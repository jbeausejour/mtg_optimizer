from .celery_app import celery_app
import time
from flask import current_app
from app.extensions import db
from app.models.scan import Scan, ScanResult
from app.models.card import MarketplaceCard
from app.models.site import Site
from app.utils.optimization import PurchaseOptimizer
from app.utils.data_fetcher import ExternalDataSynchronizer
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

@celery_app.task(bind=True)
def optimize_cards(self, card_list_dicts, site_ids):
    try:
        # Create a new scan
        new_scan = Scan()
        db.session.add(new_scan)
        db.session.commit()

        # Fetch full card objects and sites
        cards = MarketplaceCard.query.filter(MarketplaceCard.id.in_([card['id'] for card in card_list_dicts])).all()
        sites = Site.query.filter(Site.id.in_(site_ids)).all()

        self.update_state(state='PROGRESS', meta={'status': 'Fetched cards and sites'})

        # Prepare optimization config
        config = {
            'filename': f'optimization_task_{new_scan.id}',
            'log_level_file': current_app.config.get('LOG_LEVEL_FILE', 'INFO'),
            'log_level_console': current_app.config.get('LOG_LEVEL_CONSOLE', 'INFO'),
            'special_site_flag': current_app.config.get('SPECIAL_SITE_FLAG', True),
            'milp_strat': current_app.config.get('MILP_STRAT', True),
            'hybrid_strat': current_app.config.get('HYBRID_STRAT', False),
            'nsga_algo_strat': current_app.config.get('NSGA_ALGO_STRAT', False),
            'min_store': current_app.config.get('MIN_STORE', 1),
            'find_min_store': current_app.config.get('FIND_MIN_STORE', False)
        }

        self.update_state(state='PROGRESS', meta={'status': 'Running optimization'})
        results = PurchaseOptimizer.run_optimization(cards, sites, config)

        self.update_state(state='PROGRESS', meta={'status': 'Saving results'})
        for result in results:
            scan_result = ScanResult(
                scan_id=new_scan.id,
                card_id=result['card_id'],
                site_id=result['site_id'],
                price=result['price']
            )
            db.session.add(scan_result)
        
        db.session.commit()

        return {
            'status': 'Optimization completed',
            'scan_id': new_scan.id
        }
    
    except Exception as e:
        logger.exception("Error during optimization")
        self.update_state(state='FAILURE', meta={'status': f'Error: {str(e)}'})
        db.session.rollback()
        return {'status': 'Failed', 'error': str(e)}

@celery_app.task
def cleanup_old_scans():
    try:
        days_to_keep = current_app.config.get('SCAN_RETENTION_DAYS', 30)
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        old_scans = Scan.query.filter(Scan.created_at < cutoff_date).all()
        
        for scan in old_scans:
            db.session.delete(scan)
        
        db.session.commit()
        logger.info(f"Cleaned up {len(old_scans)} old scans")
        return {'status': 'Cleanup completed', 'scans_removed': len(old_scans)}
    except Exception as e:
        logger.exception("Error during cleanup")
        db.session.rollback()
        return {'status': 'Failed', 'error': str(e)}

@celery_app.task(bind=True)
def start_scraping_task(self, site_ids, card_names):
    logger.info("start_scraping_task is running")
    self.update_state(state='PROCESSING', meta={'status': 'Initializing scraping task'})
    
    try:
        sites = Site.query.filter(Site.id.in_(site_ids)).all()
        
        scraper = ExternalDataSynchronizer()
        results = scraper.scrape_multiple_sites(sites, card_names)
        
        self.update_state(state='PROCESSING', meta={'status': 'Saving results to database'})
        scraper.save_results_to_db(results)
        
        return {'status': 'Scraping completed', 'sites_scraped': len(sites), 'cards_scraped': len(card_names)}
    except Exception as e:
        self.update_state(state='FAILURE', meta={'status': f'Error: {str(e)}'})
        raise

@celery_app.task(bind=True)
def test_task(self):
    logger.info("Test task is running")
    total = 10
    for i in range(total):
        time.sleep(1)  # Simulate a time-consuming task
        self.update_state(state='PROGRESS', meta={'status': f'Processing {i+1}/{total}'})
    return {'status': 'Task completed!', 'result': 42}
    # return "Hello, Celery!"
