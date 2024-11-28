import logging
from datetime import datetime, timezone
import pandas as pd
from sqlalchemy.orm import Query
from flask import current_app
from app.extensions import db
from app.models.scan import Scan, ScanResult
from app.models.site import Site
from app.utils.data_fetcher import ExternalDataSynchronizer
from app.utils.optimization import PurchaseOptimizer
from app.models.card import UserBuylistCard
from .celery_app import celery_app
from celery import states
from celery.exceptions import SoftTimeLimitExceeded, TimeLimitExceeded
import asyncio
from sqlalchemy import select, text  # Add this import
from app.services.scan_service import ScanService
from app.dto.optimization_dto import OptimizationConfigDTO, OptimizationResultDTO, ScanResultDTO


logger = logging.getLogger(__name__)

def is_data_fresh(card_name):
    """Check if the card data is fresh (less than 24 hours old)"""
    scan_result = ScanResult.query.filter_by(name=card_name).order_by(ScanResult.updated_at.desc()).first()
    
    if not scan_result:
        return False
        
    now = datetime.now(timezone.utc).replace(microsecond=0)
    age = now - scan_result.updated_at.replace(tzinfo=timezone.utc, microsecond=0)
    return age.total_seconds() < 24 * 3600


class OptimizationTaskManager:
    def __init__(self, site_ids, card_list, strategy, min_store, find_min_store):
        self.site_ids = site_ids
        self.card_list = card_list
        self.strategy = strategy
        self.min_store = min_store
        self.find_min_store = find_min_store
        self.sites = Site.query.filter(Site.id.in_(site_ids)).all()
        self.card_names = [card['name'] for card in card_list if 'name' in card]
        self.logger = logger  # Use the global logger instead of creating a new one

    def handle_scraping(self):
        outdated_cards = [card for card in self.card_list if not is_data_fresh(card['name'])]
        if not outdated_cards:
            return None

        scraper = ExternalDataSynchronizer()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            results = loop.run_until_complete(
                scraper.scrape_multiple_sites(self.sites, self.card_names, strategy=self.strategy)
            )
            return results
        finally:
            loop.close()

    def prepare_optimization_data(self):
        try:
            latest_scan = Scan.query.order_by(Scan.id.desc()).first()
            if not latest_scan:
                logger.error("No latest scan found")
                return None, None

            # Get scan results and convert to card_listings_df
            results = db.session.query(ScanResult).filter(
                ScanResult.scan_id == latest_scan.id
            ).all()

            if not results:
                logger.error("No scan results found")
                return None, None

            # Create a site_id to site_name mapping
            site_mapping = {site.id: site.name for site in self.sites}

            # Create card_listings_df with standardized structure
            card_listings_df = pd.DataFrame([{
                'name': r.name,
                'site': site_mapping.get(r.site_id, ''),  # Changed from site_name to site to match mapping
                'price': float(r.price),
                'quality': r.quality,
                'quantity': int(r.quantity),
                # Optional columns
                'set_name': r.set_name,
                'version': r.version,
                'foil': bool(r.foil),
                'language': r.language,
                'site_id': r.site_id,
                'weighted_price': float(r.price)
            } for r in results])

            # Validate required columns are present
            required_columns = ['name', 'site', 'price', 'quality', 'quantity']
            missing_columns = [col for col in required_columns if col not in card_listings_df.columns]
            if missing_columns:
                logger.error(f"Missing required columns: {missing_columns}")
                return None, None

            # Create quality weights mapping
            quality_weights = {
                "NM": 1.0,
                "LP": 1.3,
                "MP": 1.7,
                "HP": 2.5,
                "DMG": 999999
            }

            # Normalize quality strings before applying weights
            card_listings_df['quality'] = card_listings_df['quality'].str.upper()
            
            # Apply quality weights with case-insensitive matching
            card_listings_df['weighted_price'] = card_listings_df.apply(
                lambda row: row['price'] * quality_weights.get(row['quality'].upper(), 1.0), 
                axis=1
            )

            # Create user_wishlist_df from card_list
            user_wishlist_df = pd.DataFrame(self.card_list)

            # Filter out cards with zero quantity
            card_listings_df = card_listings_df[card_listings_df['quantity'] > 0]

            # Verify data availability
            if card_listings_df.empty:
                logger.error("No valid card data after filtering")
                return None, None

            # Match format expected by optimizer
            filtered_listings_df = card_listings_df.copy()
            filtered_listings_df = filtered_listings_df.sort_values(['name', 'weighted_price'])

            logger.info(f"Prepared data: {len(filtered_listings_df)} card variants across {filtered_listings_df['site_id'].nunique()} sites")
            return filtered_listings_df, user_wishlist_df

        except Exception as e:
            logger.exception(f"Error in prepare_optimization_data: {str(e)}")
            return None, None

    def run_optimization(self, filtered_listings_df, user_wishlist_df):
        """Run optimization with the prepared data"""
        try:
            if filtered_listings_df is None or user_wishlist_df is None:
                self.logger.error("Invalid input data for optimization")
                return None
            
            config = {
                "milp_strat": self.strategy == "milp",
                "nsga_algo_strat": self.strategy == "nsga-ii",
                "hybrid_strat": self.strategy == "hybrid",
                "min_store": self.min_store,
                "find_min_store": self.find_min_store,
            }
            
            optimizer = PurchaseOptimizer(
                filtered_listings_df, 
                user_wishlist_df,
                config=config
            )
            
            # Pass the required parameters to run_optimization
            return optimizer.run_optimization(self.card_names, self.sites, config)
            
        except Exception as e:
            self.logger.error(f"Error in run_optimization: {str(e)}")
            return None

@celery_app.task(bind=True, soft_time_limit=3600, time_limit=3660)
def start_scraping_task(self, site_ids, card_list, strategy, min_store, find_min_store):
    # Create config DTO for validation
    config = OptimizationConfigDTO(strategy=strategy, min_store=min_store, find_min_store=find_min_store)
    task_manager = OptimizationTaskManager(site_ids, card_list, config.strategy, 
                                         config.min_store, config.find_min_store)
    logger = task_manager.logger

    try:
        self.update_state(state="PROCESSING", meta={"status": "Task initialized", "progress": 0})

        # Handle scraping
        scraping_results = task_manager.handle_scraping()
        self.update_state(state="PROCESSING", meta={"status": "Scraping complete", "progress": 25})

        # Prepare optimization data
        filtered_listings_df, user_wishlist_df = task_manager.prepare_optimization_data()
        
        # Check if DataFrame is empty using the proper pandas method
        if filtered_listings_df is None or filtered_listings_df.empty:
            logger.error("No card details available for optimization")
            return {"status": "Failed", "message": "No card details available for optimization"}
        
        logger.info(f"Starting optimization with {len(filtered_listings_df)} cards")
        self.update_state(state="PROCESSING", meta={"status": "Running optimization", "progress": 75})

        # Run optimization with empty buylist if none provided
        optimization_results = task_manager.run_optimization(
            filtered_listings_df, 
            user_wishlist_df if user_wishlist_df is not None else pd.DataFrame()
        )
        
        if optimization_results is None:
            return OptimizationResultDTO(
                status="Completed",
                message="No optimization results found",
                sites_scraped=len(task_manager.sites),
                cards_scraped=len(card_list),
                optimization={},
                progress=100
            ).__dict__

        return OptimizationResultDTO(
            status="Completed",
            sites_scraped=len(task_manager.sites),
            cards_scraped=len(card_list),
            optimization=optimization_results,
            progress=100
        ).__dict__

    except Exception as e:
        logger.exception("Error during task execution")
        self.update_state(state=states.FAILURE, 
                         meta={"exc_type": type(e).__name__, 
                              "exc_message": str(e)})
        raise


# Remove async from optimize_cards task
@celery_app.task(bind=True)
def optimize_cards(self, card_list_dicts, site_ids):
    try:
        # Create a new scan using the service
        new_scan = ScanService.create_scan()

        # Fetch full card objects and sites
        cards = UserBuylistCard.query.filter(
            UserBuylistCard.id.in_([card["id"] for card in card_list_dicts])
        ).all()
        sites = Site.query.filter(Site.id.in_(site_ids)).all()

        self.update_state(state="PROGRESS", meta={
                          "status": "Fetched cards and sites"})

        self.update_state(state="PROGRESS", meta={
                          "status": "Running optimization"})
        
        scraper = ExternalDataSynchronizer()
        all_results = []

        for site in sites:
            # Use the strategy defined for each site to scrape the card prices
            strategy = site.method  # Assuming each Site has a 'strategy' attribute
            self.update_state(state="PROGRESS", meta={
                              "status": f"Scraping data for site {site.name} with strategy {strategy}"})

            # Scrape card prices for this specific site
            site_results = scraper.scrape_multiple_sites([site], cards, strategy=strategy)
            all_results.extend(site_results)

        self.update_state(state="PROGRESS", meta={"status": "Saving results"})

        # Save the scraped results using the service
        for result in all_results:
            ScanService.save_scan_result(new_scan.id, result)

        db.session.commit()

        return {"status": "Optimization completed", "scan_id": new_scan.id}

    except Exception as e:
        logger.exception("Error during optimization")
        self.update_state(state="FAILURE", meta={"status": f"Error: {str(e)}"})
        db.session.rollback()
        return {"status": "Failed", "error": str(e)}
