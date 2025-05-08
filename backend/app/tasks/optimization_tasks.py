import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

import pandas as pd
from sqlalchemy import select
from app import create_app
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.utils.async_context_manager import celery_session_scope
from app.constants.card_mappings import CardQuality
from app.dto.optimization_dto import (
    CardInSolution,
    OptimizationConfigDTO,
    OptimizationResultDTO,
    OptimizationSolution,
    StoreInSolution,
)

from app.models.site import Site
from app.models.site_statistics import SiteStatistics
from app.services.site_service import SiteService
from app.services.card_service import CardService
from app.services.optimization_service import OptimizationService
from app.services.scan_service import ScanService
from app.tasks.celery_instance import celery_app
from app.utils.data_fetcher import ErrorCollector, ExternalDataSynchronizer, SiteScrapeStats
from app.utils.optimization import PurchaseOptimizer
from celery import states

logger = logging.getLogger(__name__)


def get_fresh_scan_results(fresh_cards, site_ids):
    """Get the latest scan results"""
    return ScanService.get_latest_scan_results_by_site_and_cards(fresh_cards, site_ids)


class OptimizationTaskManager:
    def __init__(self, site_ids, sites, card_list_from_frontend, strategy, min_store, find_min_store):
        self.site_ids = site_ids
        self.card_list_from_frontend = card_list_from_frontend
        self.strategy = strategy
        self.min_store = min_store
        self.find_min_store = find_min_store
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

            start_time = time.time()  # Start timing
            logger.info(f"Processing {len(scraping_results)} scraping results")
            card_listings = self._process_scraping_results(scraping_results)
            elapsed_time = round(time.time() - start_time, 2)  # Compute elapsed time

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
            filtered_listings_df = self._process_listings_dataframe(card_listings_df)
            logger.info(f"Filtered listings processed: {len(filtered_listings_df)}")
            user_wishlist_df = pd.DataFrame(self.card_list_from_frontend)
            logger.info(f"User wishlist listings: {len(user_wishlist_df)}")

            # Ensure min_quality is included in user_wishlist_df
            if "quality" in user_wishlist_df.columns:
                user_wishlist_df.rename(columns={"quality": "min_quality"}, inplace=True)
            else:
                user_wishlist_df["min_quality"] = "NM"  # Default to 'NM' if not provided

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

            # Directly trust set_code here:
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
                    # "weighted_price": round(float(r["price"]), 2),
                }
            )
        return card_listings

    def _get_scan_id(self):
        """Get current or latest scan ID"""
        if self.current_scan_id:
            return self.current_scan_id
        latest_scan = ScanService.get_latest_scan_results()
        # latest_scan = Scan.query.order_by(Scan.id.desc()).first()
        return latest_scan.id if latest_scan else None

    def _fetch_scan_results(self, scan_id):
        """Fetch scan results from database"""
        scan_results = ScanService.get_scan_results_by_id_and_sites(scan_id, site_ids=self.site_ids)
        return scan_results

    def _process_listings_dataframe(self, df):
        """Process and filter the card listings DataFrame"""
        if df.empty:
            return None

        # Step 1: Define the quality weights once at the top (if not already)
        quality_weights = {"NM": 1.0, "LP": 0.9, "MP": 0.8, "HP": 0.3, "DMG": 0.1}
        mapping = CardQuality.get_upper_mapping()
        # Step 2: Normalize quality efficiently (fully vectorized, no apply)
        df["quality"] = df["quality"].str.strip().str.upper().map(mapping).fillna("NM")

        # Step 3: Calculate weighted_price (fully vectorized)
        df["weighted_price"] = df["price"] * df["quality"].map(quality_weights).fillna(1.0)

        # Filter and sort
        filtered_df = df[df["quantity"] > 0].copy()
        return filtered_df.sort_values(["name", "weighted_price"])

    @staticmethod
    def display_statistics(filtered_listings_df):

        sites_stats = {}
        # Populate site_stats with the required keys
        for site in filtered_listings_df["site_name"].unique():
            site_data = filtered_listings_df[filtered_listings_df["site_name"] == site]
            nbr_cards_in_buylist = site_data["name"].nunique()
            total_cards = site_data["quantity"].sum()
            min_price = site_data["price"].min()
            max_price = site_data["price"].max()
            avg_price = site_data["price"].mean()
            sum_cheapest = site_data.groupby("name")["price"].min().sum()

            # Calculate quality distribution
            quality_counts = site_data["quality"].value_counts().to_dict()
            quality_distribution = ", ".join([f"{q}({c})" for q, c in quality_counts.items()])

            sites_stats[site] = {
                "nbr_cards_in_buylist": nbr_cards_in_buylist,
                "total_cards": total_cards,
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
                total_cards = stats["total_cards"]
                min_price = stats["min_price"]
                max_price = stats["max_price"]
                avg_price = stats["avg_price"]
                sum_cheapest = stats["sum_cheapest"]
                quality_distribution = stats["quality_distribution"]

                logger.info(
                    f"{site:<25} {nbr_cards_in_buylist:<8} {total_cards:<12} {min_price:<7.2f} {max_price:<7.2f} "
                    f"{avg_price:<7.2f} {sum_cheapest:<7.2f} {quality_distribution}"
                )
            except KeyError as e:
                logger.error(f"Missing key {e} in site stats for {site}")

        logger.info("=" * 120)

        return len(sites_stats)

    async def run_optimization(self, filtered_listings_df, user_wishlist_df, celery_task=None):
        """Run optimization with the prepared data"""

        logger.info("=== Starting Optimization Process ===")

        # Add site statistics debugging
        if not filtered_listings_df.empty:
            logger.info(f"Total filtered listings: {len(filtered_listings_df)}")

            max_store = self.display_statistics(filtered_listings_df)

        try:
            if filtered_listings_df is None or user_wishlist_df is None:
                self.logger.error("Invalid input data for optimization")
                return None

            # Add site information to the DataFrame
            filtered_listings_df["site_info"] = filtered_listings_df["site_id"].map(lambda x: self.site_data.get(x, {}))

            config = {
                "milp_strat": self.strategy == "milp",
                "nsga_strat": self.strategy == "nsga-ii",
                "hybrid_strat": self.strategy == "hybrid",
                "min_store": self.min_store,
                "find_min_store": self.find_min_store,
                "max_store": max_store,  # Introduce a maximum number of stores to use
            }

            optimizer = PurchaseOptimizer(filtered_listings_df, user_wishlist_df, config=config)

            optimization_results = optimizer.run_optimization(self.card_names, config, celery_task)

            # Collect errors from ErrorCollector
            error_collector = ErrorCollector.get_instance()
            optimization_results["errors"] = {
                "unreachable_stores": list(error_collector.unreachable_stores),
                "unknown_languages": list(error_collector.unknown_languages),
                "unknown_qualities": list(error_collector.unknown_qualities),
            }

            # Log collected errors
            if error_collector.unreachable_stores:
                logger.warning("Unreachable stores:")
                for store in sorted(error_collector.unreachable_stores):
                    logger.warning(f"  - {store}")

            if error_collector.unknown_languages:
                logger.warning("Unknown languages found:")
                for lang in sorted(error_collector.unknown_languages):
                    logger.warning(f"  - {lang}")

            if error_collector.unknown_qualities:
                logger.warning("Unknown qualities found:")
                for quality in sorted(error_collector.unknown_qualities):
                    logger.warning(f"  - {quality}")

            logger.info("=== Optimization Process Completed ===")
            return optimization_results

        except Exception as e:
            self.logger.error(f"Error in run_optimization: {str(e)}")
            self.logger.error(
                f"DataFrame info: {filtered_listings_df.info() if filtered_listings_df is not None else None}"
            )
            return None


def serialize_results(obj):
    """Custom serializer for handling special types"""
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    elif hasattr(obj, "__dict__"):
        return {k: serialize_results(v) for k, v in obj.__dict__.items() if not k.startswith("_") and not callable(v)}
    elif isinstance(obj, (list, tuple)):
        return [serialize_results(k) for k, v in obj.items()]
    elif pd.isna(obj):  # Handle NaN/None values
        return None
    elif hasattr(obj, "item"):  # Handle numpy types
        return obj.item()
    elif callable(obj):  # Handle methods/functions
        return None
    return obj


def _get_site_queue(site):
    """Determine the appropriate queue for a site based on its scraping method"""
    method = site.method.lower()
    site_id = site.id

    if method == "crystal":
        # Distribute crystal sites between two workers
        if site_id % 2 == 0:  # Even IDs go to crystal_1
            return "site_crystal_1"
        else:  # Odd IDs go to crystal_2
            return "site_crystal_2"
    elif method == "shopify":
        return "site_shopify"
    elif method == "f2f":
        return "site_f2f"
    elif method == "scrapper":
        return "site_scrapper"
    else:
        return "site_other"


@celery_app.task(bind=True, soft_time_limit=1800, time_limit=1860)
def scrape_site_task(self, site_id, card_names, scan_id):
    """Task to scrape a single site."""
    if not hasattr(self, "progress"):
        self.progress = 0

    result = {"site_id": site_id, "site_name": "Unknown", "count": 0, "error": None}

    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(_async_scrape_site(self, site_id, card_names, scan_id, result))
    except RuntimeError as e:
        # Handle "event loop is closed" error
        logger.warning(f"Retrying scrape_site_task due to closed loop: {e}")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(_async_scrape_site(self, site_id, card_names, scan_id, result))
    except Exception as e:
        logger.exception(f"Fatal error in scrape_site_task for site {site_id}: {e}")
        result["error"] = str(e)
        return result


async def _async_scrape_site(celery_task, site_id, card_names, scan_id, result):
    """Async implementation of the scrape site task."""
    try:
        # Get the site data from the database
        async with celery_session_scope() as session:
            site_query = await session.execute(select(Site).filter(Site.id == site_id))
            site = site_query.scalars().first()

            if not site:
                logger.error(f"Site with ID {site_id} not found")
                result["error"] = "Site not found"
                return result

            # Store site data in dictionary to avoid session dependency
            site_data = {
                "id": site.id,
                "name": site.name,
                "method": site.method,
                "url": site.url,
                "api_url": site.api_url,
            }

            # Update result with site name
            result["site_name"] = site.name

        # Create scraper and stats objects
        scraper = ExternalDataSynchronizer()
        stats = SiteScrapeStats()

        # Run the scraping with site_data instead of site
        scraping_results = await scraper.process_site(site_data, card_names, stats, 0, celery_task)

        # Save results to database
        if scraping_results:
            async with celery_session_scope() as session:
                for card_result in scraping_results:
                    await ScanService.create_scan_result(session, scan_id, card_result)

                await stats.persist_to_db(session, scan_id)
                await session.commit()
            result["count"] = len(scraping_results)
            logger.info(f"Site {site_data['name']} completed with {len(scraping_results)} results")
        else:
            logger.warning(f"No results found for site {site_data['name']}")

        # Clean up scraper resources if needed
        if hasattr(scraper, "__aexit__"):
            await scraper.__aexit__(None, None, None)

        # Return the result
        return result

    except Exception as e:
        logger.exception(f"Error in _async_scrape_site for site {site_id}: {str(e)}")
        result["error"] = str(e)
        return result


@celery_app.task(bind=True, soft_time_limit=3600, time_limit=3660)
def start_scraping_task(self, *args, **kwargs):
    if not hasattr(self, "progress"):
        self.progress = 0
    logger.info("start_scraping_task started")

    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(_async_start_scraping_task(self, *args, **kwargs))
    except RuntimeError as e:
        logger.warning(f"Retrying start_scraping_task due to closed loop: {e}")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(_async_start_scraping_task(self, *args, **kwargs))
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
    celery_task,
    site_ids,
    card_list_from_frontend,
    strategy,
    min_store,
    find_min_store,
    min_age_seconds,
    buylist_id,
    user_id,
    strict_preferences,
    user_preferences,
) -> Dict:
    """Async implementation of the start_scraping_task"""

    def update_progress(status: str, progress: float, details: Optional[dict] = None):
        celery_task.progress = progress
        celery_task.update_state(
            state="PROCESSING",
            meta={"status": status, "progress": progress, **({"details": details} if details else {})},
        )

    try:
        logger.info("_async_start_scraping_task started")
        total_start_time = time.time()
        config = OptimizationConfigDTO(
            strategy=strategy,
            min_store=min_store,
            find_min_store=find_min_store,
            buylist_id=buylist_id,
            user_id=user_id,
            strict_preferences=strict_preferences,
            user_preferences=user_preferences,
        )

        # Initialize scan
        scan_id = await _initialize_scan(buylist_id, celery_task)

        # Evaluate freshness
        card_names = [card["name"] for card in card_list_from_frontend]
        fresh_cards, outdated_cards = await _evaluate_card_freshness(card_names, min_age_seconds)

        logger.info(f"Found {len(fresh_cards)} fresh, {len(outdated_cards)} outdated cards")
        celery_task.progress = 10
        update_progress("Retrieving fresh card data", celery_task.progress)

        # Retrieve fresh results
        all_results = []
        if fresh_cards:
            all_results.extend(await _get_fresh_card_results(fresh_cards, site_ids))

        # Scrape outdated cards
        if outdated_cards:
            await _launch_and_track_scraping_tasks(celery_task, outdated_cards, site_ids, scan_id)

        celery_task.progress = 55
        update_progress("Retrieving scraping results", celery_task.progress)

        # Build final scan result set
        new_results = await _build_final_results(scan_id, outdated_cards)
        all_results.extend(new_results)

        # Log scrape statistics
        await _log_scrape_statistics(scan_id)

        # Run optimization
        result = await _optimize_and_return_result(
            celery_task, config, card_list_from_frontend, all_results, site_ids, scan_id, total_start_time
        )
        return result
    except Exception as e:
        logger.exception(f"Error in _async_start_scraping_task: {str(e)}")
        raise


async def _initialize_scan(buylist_id, celery_task):

    async with celery_session_scope() as session:
        scan = await ScanService.create(session, buylist_id=buylist_id)
        await session.commit()
        celery_task.progress = 5
        celery_task.update_state(state="PROCESSING", meta={"status": "Created scan"})
    return scan.id


async def _evaluate_card_freshness(card_names, min_age_seconds):
    fresh, outdated = [], []
    now = datetime.now(timezone.utc).replace(microsecond=0)

    async with celery_session_scope() as session:
        for name in card_names:
            updated_at = await ScanService.get_latest_scan_updated_at_by_card_name(session, name)
            if updated_at and (now - updated_at).total_seconds() < min_age_seconds:
                fresh.append(name)
            else:
                outdated.append(name)

    return fresh, outdated


async def _get_fresh_card_results(fresh_cards, site_ids):
    async with celery_session_scope() as session:
        results = await ScanService.get_latest_scan_results_by_site_and_cards(session, fresh_cards, site_ids)
        return [r.to_dict() for r in results]


async def _launch_and_track_scraping_tasks(celery_task, outdated_cards, site_ids, scan_id):
    async with celery_session_scope() as session:
        sites = await SiteService.get_sites_by_ids(session, site_ids)

    progress_increment = 30 / len(sites) if sites else 0
    site_tasks = []

    for idx, site in enumerate(sites):
        queue = _get_site_queue(site)
        task = scrape_site_task.apply_async(
            kwargs={"site_id": site.id, "card_names": outdated_cards, "scan_id": scan_id}, queue=queue
        )
        site_tasks.append(task)
        celery_task.progress = 15 + ((idx + 1) * progress_increment)
        celery_task.update_state(state="PROCESSING", meta={"status": f"Dispatched {idx + 1}/{len(sites)}"})

    completed = 0
    while completed < len(site_tasks):
        completed = sum(1 for t in site_tasks if t.ready())
        await asyncio.sleep(2)


async def _build_final_results(scan_id, outdated_cards):
    """
    Fetches and prepares scan results safely within the session context.
    """

    async with celery_session_scope() as session:
        scan = await ScanService.get_scan_results_by_scan_id(session, scan_id)
        if not scan:
            logger.error(f"Scan ID {scan_id} not found in DB.")
            raise ValueError(f"Could not fetch scan with ID {scan_id}")

        # Ensure scan_results are loaded and processed within the session
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
                        # Optional: add "site_name" here by manually joining it in a separate call if needed
                    }
                )
            except Exception as e:
                logger.warning(f"Skipping result due to error: {e} for card {r.name}")

    return filtered_results


async def _log_scrape_statistics(scan_id):
    async with celery_session_scope() as session:
        result = await session.execute(
            select(SiteStatistics)
            .options(selectinload(SiteStatistics.site))  # <-- critical fix
            .filter(SiteStatistics.scan_id == scan_id)
        )
        stats = result.scalars().all()
        SiteScrapeStats.from_db(stats).log_summary(logger)


async def _optimize_and_return_result(celery_task, config, cards, all_results, site_ids, scan_id, start_time):

    async with celery_session_scope() as session:
        celery_task.progress = 60
        sites = (await session.execute(select(Site).filter(Site.id.in_(site_ids)))).scalars().all()
        task_mgr = OptimizationTaskManager(
            site_ids, sites, cards, config.strategy, config.min_store, config.find_min_store
        )
        await task_mgr.initialize(session)
        listings_df, wishlist_df = await task_mgr.prepare_optimization_data(all_results)

        if listings_df is None or listings_df.empty:
            result = await handle_failure(session, "No valid card listings found", task_mgr, scan_id, config)
            session.commit()
            return result

        celery_task.progress = 70
        result = await task_mgr.run_optimization(listings_df, wishlist_df, celery_task)

        if not result or result.get("status") != "success":
            result = await handle_failure(session, "Optimization failed", task_mgr, scan_id, result, config)
            session.commit()
            return result

        celery_task.progress = 100
        elapsed = round(time.time() - start_time, 2)
        logger.info(f"Task completed in {elapsed} seconds")
        result = await handle_success(session, result, task_mgr, scan_id, config)

        await session.commit()
    return result


async def handle_success(session, optimization_result, task_manager, scan_id, config):
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
                total_qty=best_solution["total_qty"],
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
                total_qty=iteration["total_qty"],
                list_stores=iteration["list_stores"],
                missing_cards=iteration["missing_cards"],
                missing_cards_count=iteration["missing_cards_count"],
                stores=stores,
                is_best_solution=False,
            )
        )

    result_dto = OptimizationResultDTO(
        status="Completed",
        message="Optimization completed successfully",
        buylist_id=config.buylist_id,
        user_id=config.user_id,
        sites_scraped=len(task_manager.site_ids),
        cards_scraped=len(task_manager.card_list_from_frontend),
        solutions=solutions,
        errors=optimization_result.get("errors", create_empty_errors()),
    )

    # Create the optimization result in the database
    await OptimizationService.create_optimization_result(session, scan_id, result_dto)
    logger.info(f"Saved optimization result with {len(result_dto.solutions)} solutions")

    return result_dto.model_dump()


async def handle_failure(session, message, task_manager, scan_id, config, optimization_result=None):
    """Handle optimization failure with async operations"""
    result_dto = OptimizationResultDTO(
        status="Failed",
        message=message,
        buylist_id=config.buylist_id,
        user_id=config.user_id,
        sites_scraped=len(task_manager.site_ids),
        cards_scraped=len(task_manager.card_list_from_frontend),
        solutions=[],
        errors=(
            optimization_result.get("errors", create_empty_errors()) if optimization_result else create_empty_errors()
        ),
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
    except RuntimeError as e:
        # Prevent 'event loop is closed' errors when run from threads
        print(f"Asyncio error: {e}")


async def _async_refresh_cache():
    """Async implementation of cache refresh"""
    async with celery_session_scope() as session:

        await CardService.fetch_scryfall_card_names_async(session)
        await CardService.fetch_scryfall_set_codes_async(session)


def create_empty_errors() -> Dict[str, List[str]]:
    """Create default empty error structure"""
    return {"unreachable_stores": [], "unknown_languages": [], "unknown_qualities": []}
