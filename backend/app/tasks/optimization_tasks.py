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
    def __init__(self, site_ids, card_list_from_frontend, strategy, min_store, find_min_store):
        self.site_ids = site_ids
        self.card_list_from_frontend = card_list_from_frontend
        self.strategy = strategy
        self.min_store = min_store
        self.find_min_store = find_min_store
        self.sites = Site.query.filter(Site.id.in_(site_ids)).all()
        self.card_names = [card['name'] for card in card_list_from_frontend if 'name' in card]
        self.logger = logger  # Use the global logger instead of creating a new one

    def handle_scraping(self):
        outdated_cards = [card for card in self.card_list_from_frontend if not is_data_fresh(card['name'])]
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

            results = db.session.query(ScanResult).filter(
                ScanResult.scan_id == latest_scan.id
            ).all()

            if not results:
                logger.error("No scan results found")
                return None, None

            # Create a site_id to site_name mapping
            site_mapping = {site.id: site.name for site in self.sites}

            # Create card_listings_df with standardized structure
            card_listings = []
            for r in results:
                site_name = site_mapping.get(r.site_id)
                if not site_name:
                    continue  # Skip entries without valid site mapping
                
                card_listings.append({
                    'name': r.name,
                    'site_name': site_name,  # Use consistent site_name field
                    'site': site_name,       # Keep site field for compatibility
                    'price': float(r.price),
                    'quality': r.quality,
                    'quantity': int(r.quantity),
                    'set_name': r.set_name,
                    'version': r.version,
                    'foil': bool(r.foil),
                    'language': r.language,
                    'site_id': r.site_id,
                    'weighted_price': float(r.price)
                })

            # Debug logging for DataFrame columns
            card_listings_df = pd.DataFrame(card_listings)
            # logger.info(f"DataFrame columns: {card_listings_df.columns.tolist()}")
            # logger.info(f"Sample data:\n{card_listings_df[['name', 'site_name', 'site']].head()}")

            # Ensure both site and site_name columns exist and are properly set
            card_listings_df['site'] = card_listings_df['site_name']  # Ensure both columns have same values
            
            # Verify required columns
            required_columns = ['name', 'site', 'site_name', 'price', 'quality', 'quantity']
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
            user_wishlist_df = pd.DataFrame(self.card_list_from_frontend)

            # Filter out cards with zero quantity
            card_listings_df = card_listings_df[card_listings_df['quantity'] > 0]

            # Verify data availability
            if card_listings_df.empty:
                logger.error("No valid card data after filtering")
                return None, None

            # Match format expected by optimizer
            filtered_listings_df = card_listings_df.copy()
            filtered_listings_df = filtered_listings_df.sort_values(['name', 'weighted_price'])

            # Ensure site information is properly set
            if 'site_name' not in card_listings_df.columns or card_listings_df['site_name'].isna().any():
                logger.error("Missing or invalid site information in card listings")
                return None, None

            # Final validation of the DataFrame
            # logger.info(f"Final DataFrame columns: {filtered_listings_df.columns.tolist()}")
            # logger.info(f"Unique sites in data: {filtered_listings_df['site'].unique().tolist()}")
            
            # logger.info(f"Prepared data: {len(card_listings_df)} card variants across {card_listings_df['site_id'].nunique()} sites")
            return card_listings_df, user_wishlist_df

        except Exception as e:
            logger.exception(f"Error in prepare_optimization_data: {str(e)}")
            return None, None

    def run_optimization(self, filtered_listings_df, user_wishlist_df):
        """Run optimization with the prepared data"""
        try:
            if filtered_listings_df is None or user_wishlist_df is None:
                self.logger.error("Invalid input data for optimization")
                return None
            
            # Log DataFrame info before optimization
            # self.logger.info(f"Optimization input columns: {filtered_listings_df.columns.tolist()}")
            # self.logger.info(f"Site column unique values: {filtered_listings_df['site'].unique().tolist()}")
            
            # Ensure site column is properly formatted
            if 'site' not in filtered_listings_df.columns:
                filtered_listings_df['site'] = filtered_listings_df['site_name']
            
            # Create a mapping of site names to Site objects
            site_mapping = {site.name: site for site in self.sites}
            
            # Validate that all sites in the DataFrame exist in our mapping
            unique_sites = filtered_listings_df['site'].unique()
            missing_sites = [site for site in unique_sites if site not in site_mapping]
            if missing_sites:
                self.logger.error(f"Missing Site objects for sites: {missing_sites}")
                return None
                
            # Add Site objects to the DataFrame
            filtered_listings_df['site'] = filtered_listings_df['site'].map(site_mapping)
            
            config = {
                "milp_strat": self.strategy == "milp",
                "nsga_algo_strat": self.strategy == "nsga-ii",
                "hybrid_strat": self.strategy == "hybrid",
                "min_store": self.min_store,
                "find_min_store": self.find_min_store,
            }
            
            # Log configuration and site information
            # self.logger.info(f"Optimization config: {config}")
            # self.logger.info(f"Available sites: {list(site_mapping.keys())}")
            
            optimizer = PurchaseOptimizer(
                filtered_listings_df, 
                user_wishlist_df,
                config=config
            )
            
            return optimizer.run_optimization(self.card_names, config)
                
        except Exception as e:
            self.logger.error(f"Error in run_optimization: {str(e)}")
            self.logger.error(f"DataFrame info: {filtered_listings_df.info()}")
            return None

import json

def serialize_results(obj):
    """Custom serializer for handling special types"""
    if hasattr(obj, 'to_dict'):
        return obj.to_dict()
    elif hasattr(obj, '__dict__'):
        return {k: serialize_results(v) for k, v in obj.__dict__.items() 
               if not k.startswith('_') and not callable(v)}
    elif isinstance(obj, (list, tuple)):
        return [serialize_results(k) for k, v in obj.items()]
    elif pd.isna(obj):  # Handle NaN/None values
        return None
    elif hasattr(obj, 'item'):  # Handle numpy types
        return obj.item()
    elif callable(obj):  # Handle methods/functions
        return None
    return obj

@celery_app.task(bind=True, soft_time_limit=3600, time_limit=3660)
def start_scraping_task(self, site_ids, card_list_from_frontend, strategy, min_store, find_min_store):
    # Create config DTO for validation
    config = OptimizationConfigDTO(strategy=strategy, min_store=min_store, find_min_store=find_min_store)
    task_manager = OptimizationTaskManager(site_ids, card_list_from_frontend, config.strategy, 
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

        # Run optimization with empty user_wishlist if none provided
        optimization_results = task_manager.run_optimization(
            filtered_listings_df, 
            user_wishlist_df if user_wishlist_df is not None else pd.DataFrame()
        )
        
        # Convert optimization results to DTO and ensure serialization
        if optimization_results is None:
            result_dto = OptimizationResultDTO(
                status="Completed",
                message="No optimization results found",
                sites_scraped=len(task_manager.sites),
                cards_scraped=len(card_list_from_frontend),
                optimization={},
                progress=100
            )
        else:
            # Ensure optimization_results is serializable
            serialized_results = serialize_results(optimization_results)
            result_dto = OptimizationResultDTO(
                status="Completed",
                sites_scraped=len(task_manager.sites),
                cards_scraped=len(card_list_from_frontend),
                optimization=serialized_results,
                progress=100
            )

        # Convert to dict and validate serialization before returning
        result_dict = result_dto.__dict__()
        # Test if serializable
        json.dumps(result_dict)  # This will raise an error if not serializable
        return result_dict

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
