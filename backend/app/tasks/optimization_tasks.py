import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

from collections import defaultdict
import pandas as pd
from sqlalchemy import select
from app import create_app
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.utils.async_context_manager import celery_session_scope
from app.constants.card_mappings import CardQuality
from app.constants.currency_constants import apply_currency_conversion_to_listings
from app.dto.optimization_dto import (
    CardInSolution,
    OptimizationConfigDTO,
    OptimizationResultDTO,
    OptimizationSolution,
    StoreInSolution,
)
from ..services.optimization_engine import OptimizationEngine

from app.models.site import Site
from app.models.site_statistics import SiteStatistics
from app.services.site_service import SiteService
from app.services.card_service import CardService
from app.services.optimization_service import OptimizationService
from app.services.scan_service import ScanService
from app.tasks.celery_instance import celery_app
from app.utils.data_fetcher import ErrorCollector, ExternalDataSynchronizer, SiteScrapeStats
from app.utils.helpers import normalize_string
from celery.result import AsyncResult

logger = logging.getLogger(__name__)


def get_fresh_scan_results(fresh_cards, site_ids):
    """Get the latest scan results"""
    return ScanService.get_latest_scan_results_by_site_and_cards(fresh_cards, site_ids)


class TaskStateUpdater:
    """Helper class to update Celery task state using captured task ID"""

    def __init__(self, task_id):
        self.task_id = task_id
        self.progress = 0
        self.logger = logging.getLogger(__name__)

    def update_state(self, state="PROCESSING", meta=None):
        if not self.task_id:
            logger.warning("No task ID available for state update")
            return

        try:
            from celery import current_app

            logger.debug(f"[DEBUG] Updating task {self.task_id} to state={state} with meta={meta}")

            # Pass meta as the result so Celery stores it in result.info
            current_app.backend.store_result(
                self.task_id, meta, state, traceback=None, request=None  # <--- this is the critical fix
            )
        except Exception as e:
            logger.warning(f"Failed to update task state: {e}")

    def update_progress(self, progress, status, **kwargs):
        """Convenience method to update progress with proper validation"""
        # Validate and clamp progress
        progress = max(0, min(100, progress))
        self.progress = progress

        meta = {"status": str(status), "progress": int(progress), **kwargs}

        self.update_state("PROCESSING", meta)
        self.logger.debug(f"Progress update: {progress}% - {status}")


class OptimizationTaskManager:

    def __init__(self, site_ids, sites, card_list_from_frontend, optimizationConfig):
        self.site_ids = site_ids
        self.card_list_from_frontend = card_list_from_frontend
        self.optimizationConfig = optimizationConfig
        self.sites = sites
        self.site_data = {site.id: {"name": site.name, "url": site.url} for site in self.sites}
        self.card_names = [card["name"] for card in card_list_from_frontend if "name" in card]
        self.logger = logger
        self.current_scan_id = None
        self.errors = {
            "unreachable_stores": set(),
            "unknown_languages": set(),
            "unknown_qualities": set(),
        }
        self.site_currency_map = {site.id: getattr(site, "currency", "CAD") for site in self.sites}

    async def initialize(self, session: AsyncSession):
        """
        Async initialization method to load sites safely in an async context.
        """
        stmt = select(Site).filter(Site.id.in_(self.site_ids))
        result = await session.execute(stmt)
        self.sites = result.scalars().all()
        self.site_data = {
            site.id: {"name": site.name, "url": site.url, "api_url": getattr(site, "api_url", None)}
            for site in self.sites
        }

    async def prepare_optimization_data(self, scraping_results):
        """Prepare optimization data from scraping results or database"""
        try:
            card_listings = []

            start_time = time.time()
            logger.info(f"Processing {len(scraping_results)} scraping results")
            card_listings = self._process_scraping_results(scraping_results)
            elapsed_time = round(time.time() - start_time, 2)

            logger.info(f"Processed {len(card_listings)} card listings results in {elapsed_time} seconds")

            for result in scraping_results:
                if "variant_id" not in result or result["variant_id"] is None:
                    logger.warning(
                        f"Scraped card missing variant_id: {result.get('name')} from site_id: {result.get('site_id')}"
                    )

            if not card_listings:
                logger.error("No card listings created")
                return None, None

            card_listings_df = pd.DataFrame(card_listings)
            card_listings_df = apply_currency_conversion_to_listings(card_listings_df, self.site_currency_map)
            filtered_listings_df = self._normalize_and_filter_dataframe(card_listings_df)
            logger.info(f"[FILTER] Listings after processing: {len(filtered_listings_df)}")
            logger.info(f"[FILTER] Unique cards after filtering: {filtered_listings_df['name'].nunique()}")
            logger.info(f"[FILTER] Unique sites after filtering: {filtered_listings_df['site_name'].nunique()}")

            user_wishlist_df = pd.DataFrame(self.card_list_from_frontend)
            logger.info(f"User wishlist listings: {len(user_wishlist_df)}")

            # Ensure min_quality is included in user_wishlist_df
            if "quality" in user_wishlist_df.columns:
                user_wishlist_df.rename(columns={"quality": "min_quality"}, inplace=True)
            else:
                user_wishlist_df["min_quality"] = "NM"  # Default to 'NM' if not provided

            logger.info(f"[DATA] Raw card_listings_df: {len(card_listings_df)} rows")
            logger.info(f"[DATA] Raw buylist_df: {len(user_wishlist_df)} rows")
            return filtered_listings_df, user_wishlist_df

        except Exception as e:
            logger.exception(f"Error in prepare_optimization_data: {str(e)}")
            return None, None

    def _process_scraping_results(self, scraping_results):
        """Process scraping results into card listings"""
        card_listings = []
        for r in scraping_results:
            site_info = self.site_data.get(r["site_id"])
            if not site_info:
                logger.warning(f"[SITE INFO] No site info found for site_id: {r['site_id']}, skipping result.")
                continue

            if not r["set_code"] or r["set_code"] == "unknown":
                logger.warning(
                    f"[SET CODE] Unknown set code for '{r['set_name']}' at final processing stage, skipping."
                )
                continue

            card_listings.append(
                {
                    "site_name": site_info["name"],
                    "name": r["name"],
                    "set_name": r["set_name"],
                    "set_code": r["set_code"],
                    "price": round(float(r["price"]), 2),
                    "quality": r["quality"],
                    "quantity": int(r["quantity"]),
                    "version": r.get("version", "Standard"),
                    "foil": bool(r.get("foil", False)),
                    "language": r.get("language", "English"),
                    "site_id": r["site_id"],
                    "variant_id": r.get("variant_id"),
                }
            )
        return card_listings

    def _get_scan_id(self):
        """Get current or latest scan ID"""
        if self.current_scan_id:
            return self.current_scan_id
        latest_scan = ScanService.get_latest_scan_results()
        return latest_scan.id if latest_scan else None

    def _fetch_scan_results(self, scan_id):
        """Fetch scan results from database"""
        scan_results = ScanService.get_scan_results_by_id_and_sites(scan_id, site_ids=self.site_ids)
        return scan_results

    def _normalize_and_filter_dataframe(self, df):
        """Normalize and filter card listings"""
        if df.empty:
            return None

        # Step 1: Normalize all quality values
        df["quality"] = df["quality"].astype(str)
        df = CardQuality.validate_and_update_qualities(df, quality_column="quality")

        # Step 2: Filter cards with quantity > 0
        df = df[df["quantity"] > 0].copy()

        # Step 3: Sort by name and original price
        return df.sort_values(["name", "price"])

    @staticmethod
    def display_statistics(filtered_listings_df):
        sites_stats = {}
        for site in filtered_listings_df["site_name"].unique():
            site_data = filtered_listings_df[filtered_listings_df["site_name"] == site]
            nbr_cards_in_buylist = site_data["name"].nunique()
            total_cards_to_scrappe = site_data["quantity"].sum()
            min_price = site_data["price"].min()
            max_price = site_data["price"].max()
            avg_price = site_data["price"].mean()
            sum_cheapest = site_data.groupby("name")["price"].min().sum()

            # Calculate quality distribution
            quality_counts = site_data["quality"].value_counts().to_dict()
            quality_distribution = ", ".join([f"{q}({c})" for q, c in quality_counts.items()])

            sites_stats[site] = {
                "nbr_cards_in_buylist": nbr_cards_in_buylist,
                "total_cards_to_scrappe": total_cards_to_scrappe,
                "min_price": min_price,
                "max_price": max_price,
                "avg_price": avg_price,
                "sum_cheapest": sum_cheapest,
                "quality_distribution": quality_distribution,
            }

        logger.info("Sites Statistics:")
        logger.info("=" * 120)
        logger.info(
            "Site                      # Cards  Total Cards  Min $   Max $   Avg $   Sum $    Quality Distribution"
        )
        logger.info("-" * 120)

        for site, stats in sorted(
            sites_stats.items(),
            key=lambda item: item[1]["nbr_cards_in_buylist"],
            reverse=True,
        ):
            try:
                nbr_cards_in_buylist = stats["nbr_cards_in_buylist"]
                total_cards_to_scrappe = stats["total_cards_to_scrappe"]
                min_price = stats["min_price"]
                max_price = stats["max_price"]
                avg_price = stats["avg_price"]
                sum_cheapest = stats["sum_cheapest"]
                quality_distribution = stats["quality_distribution"]

                logger.info(
                    f"{site:<25} {nbr_cards_in_buylist:<8} {total_cards_to_scrappe:<12} {min_price:<7.2f} {max_price:<7.2f} "
                    f"{avg_price:<7.2f} {sum_cheapest:<7.2f} {quality_distribution}"
                )
            except KeyError as e:
                logger.error(f"Missing key {e} in site stats for {site}")

        logger.info("=" * 120)
        return len(sites_stats)


def serialize_results(obj):
    """Custom serializer for handling special types"""
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    elif hasattr(obj, "__dict__"):
        return {k: serialize_results(v) for k, v in obj.__dict__.items() if not k.startswith("_") and not callable(v)}
    elif isinstance(obj, (list, tuple)):
        return [serialize_results(k) for k, v in obj.items()]
    elif pd.isna(obj):
        return None
    elif hasattr(obj, "item"):
        return obj.item()
    elif callable(obj):
        return None
    return obj


def _get_site_queue(site):
    """Determine the appropriate queue for a site based on its scraping method"""
    method = site.method.lower()
    site_id = site.id

    if method == "crystal":
        if site_id % 2 == 0:
            return "site_crystal_1"
        else:
            return "site_crystal_2"
    elif method == "shopify":
        return "site_shopify"
    elif method == "f2f":
        return "site_f2f"
    elif method == "scrapper":
        return "site_scrapper"
    else:
        return "site_other"


@celery_app.task(bind=True, soft_time_limit=3600, time_limit=1860)
def scrape_site_task(self, site_id, card_names, scan_id):
    """Task to scrape a single site."""
    if not hasattr(self, "progress"):
        self.progress = 0
    # Capture task ID immediately
    task_id = self.request.id
    task_updater = TaskStateUpdater(task_id)

    result = {
        "site_id": site_id,
        "site_name": "Unknown",
        "count": 0,
        "error": None,
        "start_time": datetime.now(timezone.utc),
        "status": "started",
    }

    try:
        task_updater.update_state(
            state="PROCESSING",
            meta={
                "site_id": site_id,
                "site_name": result["site_name"],
                "progress": 0,
                "status": "Initializing",
                "cards_processed": 0,
                "total_cards_to_scrappe": len(card_names),
            },
        )
    except Exception as e:
        logger.warning(f"Failed to update initial task state: {e}")

    try:
        return asyncio.run(_async_scrape_site(task_updater, site_id, card_names, scan_id, result))
    except Exception as e:
        logger.exception(f"Fatal error in scrape_site_task for site {site_id}: {e}")
        result["error"] = str(e)
        result["status"] = "failed"
        result["end_time"] = datetime.now(timezone.utc)

        try:
            task_updater.update_state(
                state="PROCESSING",
                meta={
                    "site_id": site_id,
                    "site_name": result["site_name"],
                    "progress": 100,
                    "status": f"Failed: {str(e)}",
                    "error": str(e),
                },
            )
        except Exception as update_error:
            logger.error(f"Failed to update task state on error: {update_error}")

        raise e


async def _async_scrape_site(task_updater, site_id, card_names, scan_id, result):
    """Async implementation of the scrape site task."""
    try:
        async with celery_session_scope() as session:
            site_query = await session.execute(select(Site).filter(Site.id == site_id))
            site = site_query.scalars().first()

            if not site:
                logger.error(f"Site with ID {site_id} not found")
                result["error"] = "Site not found"
                result["status"] = "failed"
                return result

            site_data = {
                "id": site.id,
                "name": site.name,
                "method": site.method,
                "url": site.url,
                "api_url": site.api_url,
            }

            result["site_name"] = site.name

        task_updater.update_state(
            state="PROCESSING",
            meta={
                "site_id": site_id,
                "site_name": site.name,
                "progress": 10,
                "status": f"Scraping {site.name}",
                "cards_processed": 0,
                "total_cards_to_scrappe": len(card_names),
            },
        )

        scraper = ExternalDataSynchronizer()
        stats = SiteScrapeStats()

        def progress_callback(cards_processed, total_cards_to_scrappe, current_card_name=None):
            # Calculate progress percentage (10% for init, 80% for scraping, 10% for saving)
            if total_cards_to_scrappe > 0:
                scraping_progress = (cards_processed / total_cards_to_scrappe) * 80
                total_progress = 10 + scraping_progress
            else:
                total_progress = 50  # Default if no total

            # Clamp progress between 10 and 90
            total_progress = max(10, min(90, total_progress))

            status_message = f"Scraping {site.name}: {cards_processed}/{total_cards_to_scrappe} cards"
            if current_card_name:
                status_message += f" (processing: {current_card_name})"

            task_updater.update_progress(
                progress=total_progress,
                status=status_message,
                site_id=site_id,
                site_name=site.name,
                cards_processed=cards_processed,
                total_cards_to_scrappe=total_cards_to_scrappe,
                current_card=current_card_name,
                step="scraping_in_progress",
            )

        requested_cards = set(normalize_string(name) for name in card_names)
        attempt_status = defaultdict(bool)
        unique_cards_found = set()

        scraping_results = await scraper.process_site(site_data, card_names, stats, progress_callback=progress_callback)

        if scraping_results:
            task_updater.update_progress(
                progress=90,
                status=f"Saving {len(scraping_results)} results to database",
                site_id=site_id,
                site_name=site.name,
                cards_found=len(scraping_results),
                step="saving_results",
            )

            async with celery_session_scope() as session:
                for card_result in scraping_results:
                    name_norm = normalize_string(card_result["name"])
                    await ScanService.create_scan_result(session, scan_id, card_result)
                    unique_cards_found.add(name_norm)
                    attempt_status[name_norm] = True

                not_found_cards = requested_cards - unique_cards_found
                for card_name in not_found_cards:
                    name_norm = normalize_string(card_name)
                    attempt_status[name_norm] = False

                for name_norm, found in attempt_status.items():
                    await ScanService.create_scan_attempt(session, scan_id, site_id, name_norm, found=found)

                await stats.persist_to_db(session, scan_id)
                await session.commit()

            result["count"] = len(scraping_results)
            result["not_found_count"] = len(not_found_cards)
            logger.info(
                f"Site {site_data['name']} completed: "
                f"{len(scraping_results)} found, {len(not_found_cards)} not found"
            )
        else:
            result["status"] = "completed"
            result["count"] = 0
            logger.warning(f"No results found for site {site_data['name']}")

        result["end_time"] = datetime.now(timezone.utc)

        if hasattr(scraper, "__aexit__"):
            await scraper.__aexit__(None, None, None)
        # Final success update
        task_updater.update_progress(
            progress=100,
            status=f'Completed: {result["count"]} cards found',
            site_id=site_id,
            site_name=site.name,
            cards_found=result["count"],
            cards_not_found=result.get("not_found_count", 0),
            step="completed",
        )

        # Mark task as SUCCESS
        task_updater.update_state(
            state="SUCCESS",
            meta={
                "site_id": site_id,
                "site_name": site.name,
                "progress": 100,
                "status": f'Completed: {result["count"]} cards found',
                "cards_found": result["count"],
                "cards_not_found": result.get("not_found_count", 0),
                "step": "completed",
            },
        )
        return result

    except Exception as e:
        logger.exception(f"Error in _async_scrape_site for site {site_id}: {str(e)}")
        result["error"] = str(e)
        result["status"] = "failed"
        result["end_time"] = datetime.now(timezone.utc)

        try:
            task_updater.update_progress(
                progress=100,
                status=f"Failed: {str(e)}",
                site_id=site_id,
                site_name=result.get("site_name", "Unknown"),
                error=str(e),
                step="error",
            )
        except Exception as update_error:
            logger.error(f"Failed to update task state: {update_error}")

        raise e


@celery_app.task(bind=True, soft_time_limit=3600, time_limit=3660)
def start_scraping_task(self, *args, **kwargs):
    if not hasattr(self, "progress"):
        self.progress = 0
    # Capture task ID immediately
    task_id = self.request.id
    logger.info(f"Starting scraping task with ID: {task_id}")

    # Create task state updater
    task_updater = TaskStateUpdater(task_id)
    try:
        # Use the safe async runner
        return asyncio.run(_async_start_scraping_task(task_updater, *args, **kwargs))
    except Exception as e:
        logger.exception(f"Fatal error in start_scraping_task: {e}")
        return {
            "status": "Failed",
            "message": f"Task execution failed: {str(e)}",
            "sites_scraped": 0,
            "cards_scraped": 0,
            "solutions": [],
            "errors": {"unreachable_stores": [], "unknown_languages": [], "unknown_qualities": []},
        }


async def _async_start_scraping_task(
    task_updater,
    site_ids,
    card_list_from_frontend,
    strategy,
    min_store,
    max_store,
    find_min_store,
    min_age_seconds,
    buylist_id,
    user_id,
    strict_preferences,
    user_preferences,
    weights,
    complete_config=None,  # New parameter for complete configuration
) -> Dict:
    """Async implementation of the start_scraping_task"""

    try:
        total_start_time = time.time()

        # Create optimization config - use complete_config if provided
        if complete_config:
            # Merge with base parameters to ensure all required fields are present
            config_dict = {
                "strategy": strategy,
                "min_store": min_store,
                "max_store": max_store,
                "find_min_store": find_min_store,
                "buylist_id": buylist_id,
                "user_id": user_id,
                "strict_preferences": strict_preferences,
                "user_preferences": user_preferences,
                "weights": weights or {},
            }
            config_dict.update(complete_config)
            optimizationConfig = config_dict
        else:
            # Legacy path - create DTO
            optimizationConfig = OptimizationConfigDTO(
                strategy=strategy,
                min_store=min_store,
                max_store=max_store,
                find_min_store=find_min_store,
                buylist_id=buylist_id,
                user_id=user_id,
                strict_preferences=strict_preferences,
                user_preferences=user_preferences,
                weights=weights or {},
            )

        # Initialize scan
        card_names = [card["name"] for card in card_list_from_frontend]
        site_ids = list(map(int, site_ids))

        # Check freshness before initializing scan
        task_updater.update_progress(2.0, "Evaluating card freshness")
        fresh_pairs, outdated_pairs = await _evaluate_card_freshness(buylist_id, card_names, min_age_seconds, site_ids)

        # Initialize scan after freshness evaluation
        task_updater.update_progress(5.0, "Initializing scan")
        scan_id = await _initialize_scan(buylist_id, task_updater)

        # Organize fresh results
        fresh_by_card = defaultdict(set)
        for name, site_id in fresh_pairs:
            fresh_by_card[name.strip()].add(site_id)

        fresh_by_card = {name: {int(site_id) for site_id in sites} for name, sites in fresh_by_card.items()}
        logger.info(f"Found {len(fresh_pairs)} fresh (card,site) pairs, {len(outdated_pairs)} outdated")

        # Load fresh results from DB
        task_updater.update_progress(8.0, "Loading fresh results from database")
        all_results = []
        if fresh_by_card:
            all_card_names = list(fresh_by_card.keys())
            async with celery_session_scope() as session:
                fresh_results = await ScanService.get_latest_scan_results_by_site_and_cards(
                    session, all_card_names, site_ids
                )
                for r in fresh_results:
                    if r.name.strip() in fresh_by_card and r.site_id in fresh_by_card[r.name.strip()]:
                        all_results.append(r.to_dict())

        # Prepare scrape targets
        outdated_by_site = {}
        for name, site_id in outdated_pairs:
            site_id = int(site_id)
            outdated_by_site.setdefault(site_id, set()).add(name)

        # Launch scrapes
        if outdated_by_site:
            task_updater.update_progress(15.0, "Launching scraping tasks")
            failed_sites = await _launch_and_track_scraping_tasks(task_updater, outdated_by_site, scan_id)
            if failed_sites:
                logger.warning(f"Scraping failures detected for: {failed_sites}")

        task_updater.update_progress(45.0, "Retrieving scraping results")

        # Build final scan result set
        outdated_cards = list({name for name, _ in outdated_pairs})
        new_results = await _build_final_results(scan_id, outdated_cards)
        fetched_card_names = {r["name"] for r in new_results}
        still_missing = [c for c in outdated_cards if c not in fetched_card_names]
        if still_missing:
            logger.warning(f"[Post-Scrape] Missing listings for {len(still_missing)} cards: {still_missing}")

        all_results.extend(new_results)

        # Log scrape statistics
        await _log_scrape_statistics(scan_id)

        # Run optimization using the enhanced service
        task_updater.update_progress(60, "Starting optimization")
        result = await _optimize_and_return_result(
            task_updater, optimizationConfig, card_list_from_frontend, all_results, site_ids, scan_id, total_start_time
        )
        return result

    except Exception as e:
        logger.exception(f"Error in _async_start_scraping_task: {str(e)}")
        raise


async def _initialize_scan(buylist_id, task_updater):
    async with celery_session_scope() as session:
        scan = await ScanService.create(session, buylist_id=buylist_id)
        await session.commit()
        task_updater.progress = 5
        task_updater.update_progress(5, "Created scan", step="scan_created")
    return scan.id


async def _evaluate_card_freshness(buylist_id: int, card_names: list[str], min_age_seconds: int, site_ids: list[int]):
    fresh_pairs = []
    outdated_pairs = []
    never_scanned_pairs = []
    now = datetime.now(timezone.utc).replace(microsecond=0)

    async with celery_session_scope() as session:
        scan_attempts = await ScanService.get_latest_scan_attempts(session, card_names, site_ids)
        latest_scan = await ScanService.get_latest_scan_by_buylist(session, buylist_id)
        scan_results = {}
        if latest_scan:
            scan_results = await ScanService.get_scan_freshness_map_by_scan_id(session, latest_scan.id)

        for name in card_names:
            normalized_name = normalize_string(name)
            for site_id in site_ids:
                key = (normalized_name, site_id)

                if key in scan_attempts:
                    attempted_at = scan_attempts[key]
                    if attempted_at.tzinfo is None:
                        attempted_at = attempted_at.replace(tzinfo=timezone.utc)
                    attempted_at = attempted_at.replace(microsecond=0)

                    age_sec = (now - attempted_at).total_seconds()

                    if age_sec > min_age_seconds:
                        outdated_pairs.append(key)
                        logger.debug(f"Outdated: {key} last attempted at {attempted_at} ({age_sec} seconds old)")
                    else:
                        fresh_pairs.append(key)
                        if key in scan_results:
                            logger.debug(f"Fresh (found): {key} - {age_sec} seconds old")
                        else:
                            logger.debug(f"Fresh (not found): {key} - {age_sec} seconds old")
                else:
                    never_scanned_pairs.append(key)
                    outdated_pairs.append(key)
                    logger.debug(f"Never scanned: {key}")

    logger.info(
        f"Freshness evaluation: {len(fresh_pairs)} fresh, "
        f"{len(outdated_pairs)} outdated ({len(never_scanned_pairs)} never scanned)"
    )

    return fresh_pairs, outdated_pairs


async def _launch_and_track_scraping_tasks(task_updater, outdated_by_site: Dict[int, set], scan_id: int):
    async with celery_session_scope() as session:
        sites = await SiteService.get_sites_by_ids(session, list(outdated_by_site.keys()))

    if not sites:
        logger.warning("No sites to scrape")
        return []

    progress_increment = 30 / len(sites) if sites else 0
    site_tasks = []
    task_metadata = {}

    for idx, site in enumerate(sites):
        queue = _get_site_queue(site)
        card_names = list(outdated_by_site.get(site.id, []))

        if not card_names:
            continue

        task = scrape_site_task.apply_async(
            kwargs={"site_id": site.id, "card_names": card_names, "scan_id": scan_id},
            queue=queue,
        )
        site_tasks.append((site.name, task.id))
        task_metadata[task.id] = {
            "site_name": site.name,
            "site_id": site.id,
            "cards_count": len(card_names),
            "status": "pending",
            "progress": 0,
        }
        current_progress = 15 + ((idx + 1) * progress_increment)
        task_updater.update_progress(
            progress=current_progress,
            status=f"Dispatched {idx + 1}/{len(sites)} sites",
            subtasks=task_metadata,
            step="dispatching_subtasks",
        )

    if not site_tasks:
        logger.info("[Scraping] No sites were dispatched for scraping.")
        return []

    logger.info(f"[Scraping] Waiting for {len(site_tasks)} tasks to finish...")

    remaining = set(tid for _, tid in site_tasks)
    failed = []
    completed_count = 0
    max_wait_time = 3600
    wait_start = time.time()

    while remaining and (time.time() - wait_start) < max_wait_time:
        await asyncio.sleep(2)
        for site_name, tid in site_tasks:
            if tid not in remaining:
                continue

            res = AsyncResult(tid)
            try:
                task_state = res.state
                task_info = None

                try:
                    task_info = res.info
                except (ValueError, KeyError) as e:
                    logger.warning(f"Failed to get task info for {site_name} ({tid}): {e}")
                    task_info = None

                if task_state == "PROCESSING" and task_info:
                    task_metadata[tid].update(
                        {
                            "status": "processing",
                            "progress": task_info.get("progress", 0),
                            "details": task_info.get("status", ""),
                            "cards_processed": task_info.get("cards_processed", 0),
                        }
                    )
                elif task_state == "SUCCESS":
                    task_metadata[tid].update(
                        {
                            "status": "completed",
                            "progress": 100,
                            "cards_found": task_info.get("cards_found", 0) if task_info else 0,
                        }
                    )
                    remaining.discard(tid)
                    completed_count += 1
                    logger.info(f"[Scraping] Site '{site_name}' completed successfully.")
                elif task_state == "FAILURE":
                    task_metadata[tid].update(
                        {"status": "failed", "progress": 100, "error": str(task_info) if task_info else "Unknown error"}
                    )
                    remaining.discard(tid)
                    failed.append(site_name)
                    logger.warning(f"[Scraping] Site '{site_name}' failed: {task_info}")
                elif task_state in ["PENDING", "RETRY"]:
                    task_metadata[tid].update(
                        {
                            "status": "pending",
                            "progress": 100,
                            "details": f"Task state: {task_state}",
                        }
                    )
                else:
                    logger.debug(f"[Scraping] Unknown task state for {site_name}: {task_state}")

            except Exception as e:
                logger.error(f"Error checking task status for {site_name} ({tid}): {e}")
                task_metadata[tid].update(
                    {"status": "failed", "progress": 100, "error": f"Task status check failed: {str(e)}"}
                )
                remaining.discard(tid)
                failed.append(site_name)
                logger.warning(f"[Scraping] Site '{site_name}' failed: {res.info}")

        overall_progress = 15 + (30 * completed_count / len(site_tasks))

        task_updater.update_progress(
            progress=overall_progress,
            status=f"Scraping sites: {completed_count}/{len(site_tasks)} completed",
            current={"subtasks": task_metadata},
            completed=completed_count,
            total=len(site_tasks),
            failed=len(failed),
            step="tracking_subtasks",
        )

    if remaining and (time.time() - wait_start) >= max_wait_time:
        logger.warning(f"[Scraping] Timeout reached, {len(remaining)} tasks still pending")
        for site_name, tid in site_tasks:
            if tid in remaining:
                failed.append(site_name)
                logger.warning(f"[Scraping] Site '{site_name}' timed out")

    if failed:
        logger.warning(f"[Scraping] {len(failed)} sites failed to scrape: {failed}")

    return failed


async def _build_final_results(scan_id, outdated_cards):
    """
    Fetches and prepares scan results safely within the session context.
    """
    async with celery_session_scope() as session:
        scan = await ScanService.get_scan_results_by_scan_id(session, scan_id)
        if not scan:
            logger.error(f"Scan ID {scan_id} not found in DB.")
            raise ValueError(f"Could not fetch scan with ID {scan_id}")

        filtered_results = []
        for r in scan.scan_results:
            if r.name not in outdated_cards:
                continue
            try:
                filtered_results.append(
                    {
                        "name": r.name,
                        "price": float(r.price),
                        "site_id": r.site_id,
                        "set_name": r.set_name,
                        "set_code": r.set_code,
                        "version": r.version,
                        "foil": r.foil,
                        "quality": r.quality,
                        "language": r.language,
                        "quantity": r.quantity,
                        "variant_id": r.variant_id,
                        "updated_at": r.updated_at.isoformat(),
                    }
                )
            except Exception as e:
                logger.warning(f"Skipping result due to error: {e} for card {r.name}")

    return filtered_results


async def _log_scrape_statistics(scan_id):
    async with celery_session_scope() as session:
        result = await session.execute(
            select(SiteStatistics).options(selectinload(SiteStatistics.site)).filter(SiteStatistics.scan_id == scan_id)
        )
        stats = result.scalars().all()
        SiteScrapeStats.from_db(stats).log_summary(logger)


async def _optimize_and_return_result(
    task_updater, optimizationConfig, cards, all_results, site_ids, scan_id, start_time
):
    """Use only the enhanced optimization service"""
    async with celery_session_scope() as session:
        task_updater.progress = 60
        sites = (await session.execute(select(Site).filter(Site.id.in_(site_ids)))).scalars().all()

        logger.info("Using ENHANCED optimization service")

        # Prepare data for enhanced service
        task_mgr = OptimizationTaskManager(site_ids, sites, cards, optimizationConfig)
        await task_mgr.initialize(session)
        listings_df, user_wishlist_df = await task_mgr.prepare_optimization_data(all_results)

        if listings_df is None or listings_df.empty:
            fail_result = await handle_failure(
                session, "No valid card listings found", task_mgr, scan_id, None, optimizationConfig
            )
            await session.commit()
            return fail_result

        # Use enhanced service
        enhanced_service = OptimizationEngine()

        # Update progress
        task_updater.update_progress(65, "Running enhanced optimization", step="optimization_start")

        # Add statistics display
        if not listings_df.empty:
            logger.info(f"Total filtered listings: {len(listings_df)}")
            optimizationConfig["max_unique_store"] = task_mgr.display_statistics(listings_df)

        try:
            optimization_result = await enhanced_service.optimize_card_purchase(
                session, listings_df, user_wishlist_df, optimizationConfig, task_updater
            )

            # Enhanced service returns formatted result
            if optimization_result and optimization_result.get("status") == "success":
                task_updater.update_progress(100, "Optimization completed successfully", step="optimization_complete")
                elapsed = round(time.time() - start_time, 2)
                logger.info(f"Enhanced optimization completed in {elapsed} seconds")

                good_result = await handle_success(
                    session,
                    "Optimization completed successfully",
                    task_mgr,
                    scan_id,
                    optimization_result,
                    optimizationConfig,
                )
                await session.commit()
                return good_result
            else:
                # Enhanced optimization failed
                fail_result = await handle_failure(
                    session,
                    optimization_result.get("error", "Enhanced optimization failed"),
                    task_mgr,
                    scan_id,
                    optimization_result,
                    optimizationConfig,
                )
                await session.commit()
                return fail_result

        except Exception as e:
            logger.error(f"Enhanced optimization error: {str(e)}")
            fail_result = await handle_failure(
                session, f"Optimization error: {str(e)}", task_mgr, scan_id, None, optimizationConfig
            )
            await session.commit()
            return fail_result


@celery_app.task
def compare_optimization_algorithms(card_list, site_ids, optimization_config):
    """
    Task to compare performance between different optimization algorithms including NSGA-III.
    """

    async def run_comparison():
        async with celery_session_scope() as session:
            sites = (await session.execute(select(Site).filter(Site.id.in_(site_ids)))).scalars().all()

            task_mgr = OptimizationTaskManager(site_ids, sites, card_list, optimization_config)
            await task_mgr.initialize(session)

            # Get some test listings (you'd need to implement this)
            listings_df = pd.DataFrame()  # Would be populated with real data
            user_wishlist_df = pd.DataFrame(card_list)

            results = {
                "test_timestamp": datetime.now(timezone.utc).isoformat(),
                "problem_size": {"num_cards": len(card_list), "num_sites": len(site_ids)},
            }

            # Test different algorithms including NSGA-III
            enhanced_service = OptimizationEngine()

            algorithms = ["milp", "nsga2", "nsga3", "moead", "hybrid_milp_moead", "hybrid_milp_nsga3"]

            for algorithm in algorithms:
                start_time = time.time()

                # Override algorithm in config
                config_copy = optimization_config.copy()
                config_copy["primary_algorithm"] = algorithm

                # Add NSGA-III specific parameters if needed
                if algorithm in ["nsga3", "hybrid_milp_nsga3"]:
                    config_copy["reference_point_divisions"] = optimization_config.get("reference_point_divisions", 12)
                    config_copy["population_size"] = optimization_config.get("population_size", 300)

                try:
                    result = await enhanced_service.optimize_card_purchase(
                        session, listings_df, user_wishlist_df, config_copy
                    )
                    execution_time = time.time() - start_time

                    results[algorithm] = {
                        "success": result.get("status") == "success",
                        "execution_time": execution_time,
                        "cards_found": result.get("best_solution", {}).get("nbr_card_in_solution", 0),
                        "total_cost": result.get("best_solution", {}).get("total_price", 0),
                        "stores_used": result.get("best_solution", {}).get("number_store", 0),
                        "performance_stats": result.get("performance_stats", {}),
                        # NSGA-III specific metrics
                        "diversity_metric": result.get("performance_stats", {}).get("diversity_metric", 0),
                        "reference_points_used": result.get("performance_stats", {}).get("reference_points_used", 0),
                    }

                    # Add algorithm-specific insights
                    if algorithm in ["nsga3", "hybrid_milp_nsga3"]:
                        results[algorithm]["algorithm_type"] = "reference_point_based"
                        results[algorithm]["expected_diversity"] = "high"
                    elif algorithm in ["nsga2"]:
                        results[algorithm]["algorithm_type"] = "crowding_distance_based"
                        results[algorithm]["expected_diversity"] = "medium"
                    elif algorithm == "milp":
                        results[algorithm]["algorithm_type"] = "exact_optimization"
                        results[algorithm]["expected_diversity"] = "low"

                except Exception as e:
                    results[algorithm] = {"success": False, "error": str(e)}

            # Calculate performance rankings
            successful_results = {k: v for k, v in results.items() if isinstance(v, dict) and v.get("success", False)}

            if successful_results:
                # Rank by different criteria
                results["rankings"] = {
                    "by_speed": sorted(
                        successful_results.keys(), key=lambda x: successful_results[x]["execution_time"]
                    ),
                    "by_cost": sorted(successful_results.keys(), key=lambda x: successful_results[x]["total_cost"]),
                    "by_completeness": sorted(
                        successful_results.keys(), key=lambda x: successful_results[x]["cards_found"], reverse=True
                    ),
                    "by_diversity": sorted(
                        successful_results.keys(),
                        key=lambda x: successful_results[x].get("diversity_metric", 0),
                        reverse=True,
                    ),
                }

            # Log results
            logger.info(f"Algorithm comparison results: {results}")
            return results

    try:
        return asyncio.run(run_comparison())
    except Exception as e:
        logger.error(f"Comparison task failed: {str(e)}")
        return {"error": str(e)}


async def handle_success(session, message, task_manager, scan_id, optimization_result, optimizationConfig):
    """Handle successful optimization with async operations"""
    best_solution = optimization_result.get("best_solution", {})
    iterations = optimization_result.get("iterations", [])

    logger.info(f"handle_success: processing solution with {len(iterations) + 1} total solutions")

    # Convert solutions to DTO format
    solutions = []

    # Process best solution
    if best_solution:
        stores = []
        if isinstance(best_solution.get("stores"), list):
            for store_data in best_solution["stores"]:
                if isinstance(store_data, dict):
                    for card in store_data.get("cards", []):
                        if "variant_id" not in card or card["variant_id"] is None:
                            logger.warning(
                                f"Card missing variant_id in final solution: {card.get('name')} from {store_data.get('site_name')}"
                            )

                    stores.append(
                        StoreInSolution(
                            site_id=store_data.get("site_id"),
                            site_name=store_data.get("site_name"),
                            cards=[CardInSolution(**card) for card in store_data.get("cards", [])],
                        )
                    )
                else:
                    logger.warning(f"Skipping malformed store data: {store_data}")

        solutions.append(
            OptimizationSolution(
                total_price=best_solution["total_price"],
                number_store=best_solution["number_store"],
                nbr_card_in_solution=best_solution["nbr_card_in_solution"],
                cards_required_total=best_solution["cards_required_total"],
                list_stores=best_solution["list_stores"],
                missing_cards=best_solution["missing_cards"],
                missing_cards_count=best_solution["missing_cards_count"],
                stores=stores,
                is_best_solution=True,
            )
        )

    # Process iterations
    for iteration in iterations:
        stores = []
        if isinstance(iteration.get("stores"), list):
            for store_data in iteration["stores"]:
                if isinstance(store_data, dict):
                    stores.append(
                        StoreInSolution(
                            site_id=store_data.get("site_id"),
                            site_name=store_data.get("site_name"),
                            cards=[CardInSolution(**card) for card in store_data.get("cards", [])],
                        )
                    )
                else:
                    logger.warning(f"Skipping malformed store data in iteration: {store_data}")

        solutions.append(
            OptimizationSolution(
                total_price=iteration["total_price"],
                number_store=iteration["number_store"],
                nbr_card_in_solution=iteration["nbr_card_in_solution"],
                cards_required_total=iteration["cards_required_total"],
                list_stores=iteration["list_stores"],
                missing_cards=iteration["missing_cards"],
                missing_cards_count=iteration["missing_cards_count"],
                stores=stores,
                is_best_solution=False,
            )
        )

    result_dto = OptimizationResultDTO(
        status="Completed",
        message=message,
        buylist_id=optimizationConfig["buylist_id"],
        user_id=optimizationConfig["user_id"],
        sites_scraped=len(task_manager.site_ids),
        cards_scraped=len(task_manager.card_list_from_frontend),
        solutions=solutions,
        errors=optimization_result.get("errors", create_empty_errors()),
        algorithm_used=optimization_result.get("algorithm_used", "Unknown"),
        execution_time=optimization_result.get("execution_time"),
        performance_stats=optimization_result.get("performance_stats"),
    )

    # Create the optimization result in the database
    await OptimizationService.create_optimization_result(session, scan_id, result_dto)
    logger.info(f"Saved optimization result with {len(result_dto.solutions)} solutions")

    return result_dto.model_dump()


async def handle_failure(session, message, task_manager, scan_id, optimization_result, optimizationConfig):
    """Handle optimization failure with async operations"""
    result_dto = OptimizationResultDTO(
        status="Failed",
        message=message,
        buylist_id=optimizationConfig["buylist_id"],
        user_id=optimizationConfig["user_id"],
        sites_scraped=len(task_manager.site_ids),
        cards_scraped=len(task_manager.card_list_from_frontend),
        solutions=[],
        errors=(
            optimization_result.get("errors", create_empty_errors()) if optimization_result else create_empty_errors()
        ),
        # Fix: Add conditional checks for these fields too
        algorithm_used=optimization_result.get("algorithm_used", "Unknown") if optimization_result else "Unknown",
        execution_time=optimization_result.get("execution_time") if optimization_result else None,
        performance_stats=optimization_result.get("performance_stats") if optimization_result else None,
    )

    # Create the optimization result in the database
    await OptimizationService.create_optimization_result(session, scan_id, result_dto)
    logger.info("start_scraping_task: Optimization failed")

    return result_dto.model_dump()


@celery_app.task
def refresh_scryfall_cache():
    """Periodically refresh the Scryfall card name and set caches."""

    async def run():
        app = create_app()
        async with app.app_context():
            print("Refreshing Scryfall card name and set caches...")
            await _async_refresh_cache()
            print("Cache refresh completed")

    try:
        asyncio.run(run())
    except Exception as e:
        print(f"Asyncio error: {e}")


async def _async_refresh_cache():
    """Async implementation of cache refresh"""
    async with celery_session_scope() as session:
        await CardService.fetch_scryfall_card_names_async(session)
        await CardService.fetch_scryfall_set_codes_async(session)


def create_empty_errors() -> Dict[str, List[str]]:
    """Create default empty error structure"""
    return {"unreachable_stores": [], "unknown_languages": [], "unknown_qualities": []}
