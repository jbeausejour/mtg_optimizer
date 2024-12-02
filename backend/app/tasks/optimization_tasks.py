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
from app.services.site_service import SiteService
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
        self.site_data = {site.id: {'name': site.name, 'url': site.url} for site in self.sites}
        self.card_names = [card['name'] for card in card_list_from_frontend if 'name' in card]
        self.logger = logger
        self.current_scan_id = None

    def create_new_scan(self):
        """Create a new scan and store its ID in the instance"""
        try:
            self.current_scan_id = ScanService.create_scan()
            logger.info(f"Created new scan with ID: {self.current_scan_id}")
            return self.current_scan_id
        except Exception as e:
            logger.error(f"Error in create_new_scan: {str(e)}")
            raise

    def handle_scraping(self):
        try:
            if not self.current_scan_id:
                self.create_new_scan()

            # Check which cards need updating
            outdated_cards = []
            fresh_cards = []
            for card in self.card_list_from_frontend:
                if is_data_fresh(card['name']):
                    fresh_cards.append(card['name'])
                else:
                    outdated_cards.append(card)

            logger.info(f"Found {len(fresh_cards)} cards with fresh data and {len(outdated_cards)} outdated cards")
            
            # Get fresh results first
            fresh_results = []
            if fresh_cards:
                fresh_results = (db.session.query(ScanResult)
                               .filter(ScanResult.name.in_(fresh_cards))
                               .filter(ScanResult.site_id.in_(self.site_ids))
                               .all())
            
            if not outdated_cards:
                logger.info("All cards have fresh data, skipping scraping")
                return fresh_results

            logger.info(f"Scraping outdated cards: {[card['name'] for card in outdated_cards]}")

            scraper = ExternalDataSynchronizer()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                scan_id = self.current_scan_id
                
                new_results = loop.run_until_complete(
                    scraper.scrape_multiple_sites(
                        self.sites,
                        [card['name'] for card in outdated_cards],
                        strategy=self.strategy
                    )
                )
                if new_results:
                    for result in new_results:
                        ScanService.save_scan_result(scan_id, result)
                    logger.info(f"Saved {len(new_results)} results with scan_id {scan_id}")
                
                # Combine fresh and new results
                all_results = fresh_results + (new_results if new_results else [])
                return all_results
            finally:
                loop.close()
        except Exception as e:
            logger.exception(f"Error in handle_scraping: {str(e)}")
            db.session.rollback()
            raise

    def prepare_optimization_data(self, scraping_results=None):
        """Prepare optimization data from scraping results or database"""
        try:
            card_listings = []
            
            if scraping_results:
                card_listings = self._process_scraping_results(scraping_results)
            else:
                scan_id = self._get_scan_id()
                if scan_id:
                    results = self._fetch_scan_results(scan_id)
                    card_listings = self._process_scraping_results(results)  # Use the same method for both cases

            if not card_listings:
                logger.error("No card listings created")
                return None, None

            card_listings_df = pd.DataFrame(card_listings)
            filtered_listings_df = self._process_listings_dataframe(card_listings_df)
            user_wishlist_df = pd.DataFrame(self.card_list_from_frontend)

            return filtered_listings_df, user_wishlist_df

        except Exception as e:
            logger.exception(f"Error in prepare_optimization_data: {str(e)}")
            return None, None

    def _process_scraping_results(self, scraping_results):
        """Process scraping results into card listings"""
        card_listings = []
        for r in scraping_results:
            # Handle both dictionary and ScanResult objects
            if isinstance(r, dict):
                site_info = self.site_data.get(r['site_id'])
                if site_info:
                    card_listings.append({
                        'name': r['name'],
                        'site_name': site_info['name'],
                        'price': float(r['price']),
                        'quality': r['quality'],
                        'quantity': int(r['quantity']),
                        'set_name': r['set_name'],
                        'version': r.get('version', 'Standard'),
                        'foil': bool(r.get('foil', False)),
                        'language': r.get('language', 'English'),
                        'site_id': r['site_id'],
                        'weighted_price': float(r['price'])
                    })
            else:  # ScanResult object
                site_info = self.site_data.get(r.site_id)
                if site_info:
                    card_listings.append({
                        'name': r.name,
                        'site_name': site_info['name'],
                        'price': float(r.price),
                        'quality': r.quality,
                        'quantity': int(r.quantity),
                        'set_name': r.set_name,
                        'version': getattr(r, 'version', 'Standard'),
                        'foil': bool(getattr(r, 'foil', False)),
                        'language': getattr(r, 'language', 'English'),
                        'site_id': r.site_id,
                        'weighted_price': float(r.price)
                    })
        return card_listings

    def _get_scan_id(self):
        """Get current or latest scan ID"""
        if self.current_scan_id:
            return self.current_scan_id
        latest_scan = Scan.query.order_by(Scan.id.desc()).first()
        return latest_scan.id if latest_scan else None

    def _fetch_scan_results(self, scan_id):
        """Fetch scan results from database"""
        return (db.session.query(ScanResult)
                .filter(ScanResult.scan_id == scan_id)
                .filter(ScanResult.site_id.in_(self.site_ids))
                .all())

    def _process_listings_dataframe(self, df):
        """Process and filter the card listings DataFrame"""
        if df.empty:
            return None

        # Quality normalization and weighting
        quality_weights = {
            "NM": 1.0, "LP": 1.3, "MP": 1.7, "HP": 2.5, "DMG": 999999
        }
        
        df['quality'] = df['quality'].str.upper()
        df['weighted_price'] = df.apply(
            lambda row: row['price'] * quality_weights.get(row['quality'].upper(), 1.0), 
            axis=1
        )
        
        # Filter and sort
        filtered_df = df[df['quantity'] > 0].copy()
        return filtered_df.sort_values(['name', 'weighted_price'])

    def run_optimization(self, filtered_listings_df, user_wishlist_df):
        """Run optimization with the prepared data"""
        try:
            if filtered_listings_df is None or user_wishlist_df is None:
                self.logger.error("Invalid input data for optimization")
                return None

            # Add site information to the DataFrame
            filtered_listings_df['site_info'] = filtered_listings_df['site_id'].map(
                lambda x: self.site_data.get(x, {})
            )
            
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
            
            return optimizer.run_optimization(self.card_names, config)
                
        except Exception as e:
            self.logger.error(f"Error in run_optimization: {str(e)}")
            self.logger.error(f"DataFrame info: {filtered_listings_df.info() if filtered_listings_df is not None else None}")
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
    config = OptimizationConfigDTO(strategy=strategy, min_store=min_store, find_min_store=find_min_store)
    
    with db.session() as session:
        task_manager = OptimizationTaskManager(site_ids, card_list_from_frontend, config.strategy, 
                                             config.min_store, config.find_min_store)
        logger = task_manager.logger

        try:
            self.update_state(state="PROCESSING", meta={"status": "Task initialized", "progress": 0})
            
            scraping_results = task_manager.handle_scraping()
            self.update_state(state="PROCESSING", meta={"status": "Scraping complete", "progress": 25})
            
            filtered_listings_df, user_wishlist_df = task_manager.prepare_optimization_data(scraping_results)
            
            if filtered_listings_df is None or filtered_listings_df.empty:
                logger.error("No card details available for optimization")
                return {"status": "Failed", "message": "No card details available for optimization"}
            
            self.update_state(state="PROCESSING", meta={"status": "Running optimization", "progress": 75})
            
            optimization_results = task_manager.run_optimization(filtered_listings_df, user_wishlist_df)
            
            result_dto = OptimizationResultDTO(
                status="Completed",
                message="Optimization completed successfully" if optimization_results else "No optimization results found",
                sites_scraped=len(task_manager.sites),
                cards_scraped=len(card_list_from_frontend),
                optimization=serialize_results(optimization_results) if optimization_results else {},
                progress=100
            )

            return result_dto.__dict__()

        except Exception as e:
            logger.exception("Error during task execution")
            self.update_state(state=states.FAILURE, 
                            meta={"exc_type": type(e).__name__, 
                                 "exc_message": str(e)})
            raise