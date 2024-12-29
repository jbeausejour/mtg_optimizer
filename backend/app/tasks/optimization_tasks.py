import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
import pandas as pd
from sqlalchemy.orm import Query
from flask import current_app
from app.extensions import db
from app.models import Scan, ScanResult, OptimizationResult
from app.models.site import Site

from app.utils.data_fetcher import ErrorCollector, ExternalDataSynchronizer
from app.utils.optimization import PurchaseOptimizer
from app.services.optimization_service import OptimizationService
from .celery_app import celery_app
from celery import states
from celery.exceptions import SoftTimeLimitExceeded, TimeLimitExceeded
import asyncio
from sqlalchemy import select, text 
from app.services.scan_service import ScanService
from app.dto.optimization_dto import CardInSolution, OptimizationConfigDTO, OptimizationResultDTO, OptimizationSolution, StoreInSolution
from app.services.card_service import CardService 


logger = logging.getLogger(__name__)

def is_data_fresh(card_name):
    """Check if the card data is fresh (less than 30 minutes old)"""
    scan_result = ScanService.get_latest_filtered_scan_results(card_name)
    
    if not scan_result:
        return False
        
    now = datetime.now(timezone.utc).replace(microsecond=0)
    age = now - scan_result.updated_at.replace(tzinfo=timezone.utc, microsecond=0)
    return age.total_seconds() < 1800  # 30 minutes

def get_fresh_scan_results(fresh_cards, site_ids):
    """Get the latest scan results"""
    return ScanService.get_fresh_scan_results(fresh_cards, site_ids)


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
        self.errors = {
            'unreachable_stores': set(),
            'unknown_languages': set(),
            'unknown_qualities': set()
        }

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

            processed_combinations = set()
            # Check which cards need updating
            outdated_cards = []
            fresh_cards = []
            for card in self.card_list_from_frontend:
                if is_data_fresh(card['name']):
                    fresh_cards.append(card['name'])
                else:
                    outdated_cards.append(card)

            logger.info("=============================")
            logger.info(f"Found {len(fresh_cards)} cards with fresh data and {len(outdated_cards)} outdated cards")
            logger.info("=============================")
            # Fix: Use string join method on the list of card names
            if fresh_cards:
                logger.info(f"Fresh cards:\n - {'\n - '.join(fresh_cards)}")
                logger.info("=============================")
            
            # Get fresh results first
            fresh_results = []
            if fresh_cards:
                # Convert fresh results to dictionaries immediately
                if fresh_cards:
                    fresh_query_results = get_fresh_scan_results(fresh_cards, self.site_ids)
                    
                    # Process fresh results with deduplication
                    for r in fresh_query_results:
                        # Create unique key for card-site-condition combination
                        fresh_results.append({
                            'site_id': r.site_id,
                            'name': r.name,
                            'set_name': r.set_name,
                            'set_code': r.set_code,
                            'price': round(float(r.price), 2),
                            'version': getattr(r, 'version', 'Standard'),
                            'foil': bool(getattr(r, 'foil', False)),
                            'quality': r.quality,
                            'language': r.language,
                            'quantity': int(r.quantity)
                        })
            
            if not outdated_cards:
                logger.info("All cards have fresh data, skipping scraping :)")
                logger.info("=============================")
                return fresh_results
            
            # Fix: Same correction for outdated cards
            logger.info(f"Scraping outdated cards:\n - {'\n - '.join([card['name'] for card in outdated_cards])}")
            logger.info("=============================")

            scraper = ExternalDataSynchronizer()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                scan_id = self.current_scan_id
                
                new_results = loop.run_until_complete(
                    scraper.scrape_multiple_sites(
                        self.sites,
                        [card['name'] for card in outdated_cards]
                    )
                )
                # Deduplicate new results before saving
                deduplicated_new_results = []
                if new_results:
                    for result in new_results:
                        combo_key = (
                            result['site_id'],
                            result['name'],
                            result['set_name'],
                            result['set_code'],
                            result['price'],
                            result['version'],
                            result['foil'],
                            result['quality'],
                            result['language']
                        )
                        if combo_key not in processed_combinations:
                            processed_combinations.add(combo_key)
                            deduplicated_new_results.append(result)
                            ScanService.save_scan_result(scan_id, result)
                    
                    logger.info(f"Saved {len(deduplicated_new_results)} unique results with scan_id {scan_id}")
                
                # Combine fresh and deduplicated new results
                all_results = fresh_results + deduplicated_new_results
                logger.info(f"Total unique card-site combinations in final results: {len(processed_combinations)}")
                return all_results
            finally:
                loop.close()
        except Exception as e:
            logger.exception(f"Error in handle_scraping: {str(e)}")
            raise  # Let the outer transaction handle rollback

    def prepare_optimization_data(self, scraping_results=None):
        """Prepare optimization data from scraping results or database"""
        try:
            card_listings = []
            
            if scraping_results:
                logger.info(f"Processing {len(scraping_results)} scraping results")
                card_listings = self._process_scraping_results(scraping_results)
                logger.info(f"Processed {len(card_listings)} card listings results")
            else:
                scan_id = self._get_scan_id()
                if scan_id:
                    logger.info(f"Using scan_id {scan_id} for optimization data")
                    results = self._fetch_scan_results(scan_id)
                    logger.info(f"Fetched {len(results)} scan results")
                    card_listings = self._process_scraping_results(results)
                    logger.info(f"Processed {len(card_listings)} card listings results")

            if not card_listings:
                logger.error("No card listings created")
                return None, None

            card_listings_df = pd.DataFrame(card_listings)
            filtered_listings_df = self._process_listings_dataframe(card_listings_df)
            logger.info(f"Filtered listings processed: {len(filtered_listings_df)}")
            user_wishlist_df = pd.DataFrame(self.card_list_from_frontend)
            logger.info(f"User wishlist listings: {len(user_wishlist_df)}")

            # Ensure min_quality is included in user_wishlist_df
            if 'quality' in user_wishlist_df.columns:
                user_wishlist_df.rename(columns={'quality': 'min_quality'}, inplace=True)
            else:
                user_wishlist_df['min_quality'] = 'NM'  # Default to 'NM' if not provided

            return filtered_listings_df, user_wishlist_df

        except Exception as e:
            logger.exception(f"Error in prepare_optimization_data: {str(e)}")
            return None, None

    def _process_scraping_results(self, scraping_results):
        """Process scraping results into card listings"""
        card_listings = []
        for r in scraping_results:
            site_info = self.site_data.get(r['site_id'])
            if site_info:
                # Get set code from the set name using CardService
                set_code = CardService.get_clean_set_code(r['set_name']) if r['set_name'] else None
                
                card_listings.append({
                    'name': r['name'],
                    'site_name': site_info['name'],
                    'price': round(float(r['price']), 2),
                    'quality': r['quality'],
                    'quantity': int(r['quantity']),
                    'set_name': r['set_name'],
                    'set_code': set_code,  # Use the retrieved set code
                    'version': r.get('version', 'Standard'),
                    'foil': bool(r.get('foil', False)),
                    'language': r.get('language', 'English'),
                    'site_id': r['site_id'],
                    'weighted_price': round(float(r['price']), 2)
                })
        return card_listings

    def _get_scan_id(self):
        """Get current or latest scan ID"""
        if self.current_scan_id:
            return self.current_scan_id
        latest_scan  = ScanService.get_latest_scan_results()
        #latest_scan = Scan.query.order_by(Scan.id.desc()).first()
        return latest_scan.id if latest_scan else None

    def _fetch_scan_results(self, scan_id):
        """Fetch scan results from database"""
        scan_results = ScanService.get_scan_by_id_and_sites(scan_id, site_ids = self.site_ids)
        return scan_results

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

    @staticmethod
    def display_statistics(filtered_listings_df):

        sites_stats = {}
        # Populate site_stats with the required keys
        for site in filtered_listings_df['site_name'].unique():
            site_data = filtered_listings_df[filtered_listings_df['site_name'] == site]
            nbr_cards_in_buylist = site_data['name'].nunique()
            total_cards = site_data['quantity'].sum()
            min_price = site_data['price'].min()
            max_price = site_data['price'].max()
            avg_price = site_data['price'].mean()
            sum_cheapest = site_data.groupby('name')['price'].min().sum()
            
            sites_stats[site] = {
                'nbr_cards_in_buylist': nbr_cards_in_buylist,
                'total_cards': total_cards,
                'min_price': min_price,
                'max_price': max_price,
                'avg_price': avg_price,
                'sum_cheapest': sum_cheapest
            }

        logger.info("Available Sites Statistics:")
        logger.info("=" * 90)
        logger.info("Site                      # Cards  Total Cards  Min $   Max $   Avg $   Sum $")
        logger.info("-" * 90)
        
        for site, stats in sorted(sites_stats.items(), key=lambda item: item[1]['nbr_cards_in_buylist'], reverse=True):
            try:
                nbr_cards_in_buylist = stats['nbr_cards_in_buylist']
                total_cards = stats['total_cards']
                min_price = stats['min_price']
                max_price = stats['max_price']
                avg_price = stats['avg_price']
                sum_cheapest = stats['sum_cheapest']
                
                logger.info(f"{site:<25} {nbr_cards_in_buylist:<8} {total_cards:<12} {min_price:<7.2f} {max_price:<7.2f} {avg_price:<7.2f} {sum_cheapest:<6.2f}")
            except KeyError as e:
                logger.error(f"Missing key {e} in site stats for {site}")
        
        logger.info("=" * 80)

        return len(sites_stats)

    def run_optimization(self, filtered_listings_df, user_wishlist_df):
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
            filtered_listings_df['site_info'] = filtered_listings_df['site_id'].map(
                lambda x: self.site_data.get(x, {})
            )
            
            config = {
                "milp_strat": self.strategy == "milp",
                "nsga_strat": self.strategy == "nsga-ii",
                "hybrid_strat": self.strategy == "hybrid",
                "min_store": self.min_store,
                "find_min_store": self.find_min_store,
                "max_store": max_store  # Introduce a maximum number of stores to use
            }
            
            optimizer = PurchaseOptimizer(
                filtered_listings_df, 
                user_wishlist_df,
                config=config
            )
            
            optimization_results = optimizer.run_optimization(self.card_names, config)

            # Collect errors from ErrorCollector
            error_collector = ErrorCollector.get_instance()
            optimization_results['errors'] = {
                'unreachable_stores': list(error_collector.unreachable_stores),
                'unknown_languages': list(error_collector.unknown_languages),
                'unknown_qualities': list(error_collector.unknown_qualities)
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
            self.logger.error(f"DataFrame info: {filtered_listings_df.info() if filtered_listings_df is not None else None}")
            return None

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
def start_scraping_task(self, site_ids, card_list_from_frontend, strategy, min_store, find_min_store) -> Dict:
    """
    Execute optimization task for given cards and sites.
    Returns serialized OptimizationResultDTO.
    """
    def update_progress(status: str, progress: int):
        self.update_state(state="PROCESSING", meta={"status": status, "progress": progress})

    try:
        # Initialize configuration and managers
        config = OptimizationConfigDTO(strategy=strategy, min_store=min_store, find_min_store=find_min_store)
        task_manager = OptimizationTaskManager(site_ids, card_list_from_frontend, config.strategy, 
                                             config.min_store, config.find_min_store)
        logger = task_manager.logger
        # Scraping phase
        update_progress("Scrapping started", 20)
        scraping_results = task_manager.handle_scraping()
        if not scraping_results:
            return handle_failure("No scraping results found", task_manager)
            
        # Data preparation phase    
        update_progress("Preparing data", 40)
        filtered_listings_df, user_wishlist_df = task_manager.prepare_optimization_data(scraping_results)
        if filtered_listings_df is None or filtered_listings_df.empty:
            return handle_failure("No valid card listings found", task_manager)

        # Optimization phase
        update_progress("Running optimization", 60)
        optimization_result = task_manager.run_optimization(filtered_listings_df, user_wishlist_df)
        
        # Result processing
        update_progress("Processing results", 80)
        if optimization_result and optimization_result.get("status") == "success":
            best_solution = optimization_result.get('best_solution', {})
            iterations = optimization_result.get('iterations', [])
            
            logger.info("Optimization Result received:")
            logger.info(f"Solution's card count: {best_solution.get('nbr_card_in_solution', 0) if isinstance(best_solution, dict) else 0}")
            logger.info(f"Iterations count: {len(iterations)}")

            update_progress("Optimization completed successfully", 100)
            return handle_success(optimization_result, task_manager)
        else:
            update_progress("Optimization failed", 100)
            return handle_failure("Optimization failed", task_manager, optimization_result)

    except Exception as e:
        logger.exception("Task execution failed")
        self.update_state(state=states.FAILURE, 
                         meta={"exc_type": type(e).__name__, "exc_message": str(e)})
        raise


def handle_success(optimization_result: Dict, task_manager: OptimizationTaskManager) -> Dict:
    """Handle successful optimization"""
    best_solution = optimization_result.get('best_solution', {})
    iterations = optimization_result.get('iterations', [])
    
    logger.info(f"handle_success: processing solution with {len(iterations) + 1} total solutions")
    
    # Convert solutions to DTO format
    solutions = []
    
    # Process best solution
    if best_solution:
        stores = []
        if isinstance(best_solution.get('stores'), list):
            for store_data in best_solution['stores']:
                if isinstance(store_data, dict):
                    stores.append(StoreInSolution(
                        site_id=store_data.get('site_id'),
                        site_name=store_data.get('site_name'),
                        cards=[CardInSolution(**card) for card in store_data.get('cards', [])]
                    ))
                else:
                    logger.warning(f"Skipping malformed store data: {store_data}")
        
        solutions.append(OptimizationSolution(
            total_price=best_solution['total_price'],
            number_store=best_solution['number_store'],
            nbr_card_in_solution=best_solution['nbr_card_in_solution'],
            total_qty=best_solution['total_qty'],
            list_stores=best_solution['list_stores'],
            missing_cards=best_solution['missing_cards'],
            missing_cards_count=best_solution['missing_cards_count'],
            stores=stores,
            is_best_solution=True
        ))
    
    # Process iterations
    for iteration in iterations:
        stores = []
        if isinstance(iteration.get('stores'), list):
            for store_data in iteration['stores']:
                if isinstance(store_data, dict):
                    stores.append(StoreInSolution(
                        site_id=store_data.get('site_id'),
                        site_name=store_data.get('site_name'),
                        cards=[CardInSolution(**card) for card in store_data.get('cards', [])]
                    ))
                else:
                    logger.warning(f"Skipping malformed store data in iteration: {store_data}")
        
        solutions.append(OptimizationSolution(
            total_price=iteration['total_price'],
            number_store=iteration['number_store'],
            nbr_card_in_solution=iteration['nbr_card_in_solution'],
            total_qty=iteration['total_qty'],
            list_stores=iteration['list_stores'],
            missing_cards=iteration['missing_cards'],
            missing_cards_count=iteration['missing_cards_count'],
            stores=stores,
            is_best_solution=False
        ))

    result_dto = OptimizationResultDTO(
        status="Completed",
        message="Optimization completed successfully",
        sites_scraped=len(task_manager.sites),
        cards_scraped=len(task_manager.card_list_from_frontend),
        solutions=solutions,
        errors=optimization_result.get('errors', create_empty_errors())
    )
    
    OptimizationService.create_optimization_result(
        scan_id=task_manager.current_scan_id,
        result_dto=result_dto
    )
    logger.info(f"Saved optimization result with {len(result_dto.solutions)} solutions")
    return result_dto.model_dump()

def handle_failure(message: str, task_manager: OptimizationTaskManager, 
                optimization_result: Optional[Dict] = None) -> Dict:
    """Handle optimization failure"""
    result_dto = OptimizationResultDTO(
        status="Failed",
        message=message,
        sites_scraped=len(task_manager.sites),
        cards_scraped=len(task_manager.card_list_from_frontend),
        solutions=[],
        errors=optimization_result.get('errors', create_empty_errors()) if optimization_result 
            else create_empty_errors()
    )
    
    OptimizationService.create_optimization_result(
        scan_id=task_manager.current_scan_id,
        result_dto=result_dto
    )
    logger.info("start_scraping_task: Optimization failed")
    return result_dto.model_dump()

def create_empty_errors() -> Dict[str, List[str]]:
    """Create default empty error structure"""
    return {
        'unreachable_stores': [],
        'unknown_languages': [],
        'unknown_qualities': []
    }