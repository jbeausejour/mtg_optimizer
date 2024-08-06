from celery import shared_task
from pytz import timezone
from app.extensions import db
from app.models.scan import Scan, ScanResult
from app.models.card import MarketplaceCard
from app.models.site import Site
from app.utils.optimization import PurchaseOptimizer
from datetime import datetime, timedelta, timezone
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True)
def optimize_cards(self, card_list_dicts, site_ids):
    from app import create_app
    app = create_app()
    with app.app_context():
        try:
            # Create a new scan
            new_scan = Scan()
            db.session.add(new_scan)
            db.session.commit()

            # Fetch full card objects and sites
            cards = MarketplaceCard.query.filter(MarketplaceCard.id.in_([card['id'] for card in card_list_dicts])).all()
            sites = Site.query.filter(Site.id.in_(site_ids)).all()

            # Update task state
            self.update_state(state='PROGRESS', meta={'status': 'Fetched cards and sites'})

            # Prepare optimization config
            config = {
                'filename': f'optimization_task_{new_scan.id}',
                'log_level_file': 'INFO',
                'log_level_console': 'INFO',
                'special_site_flag': True,
                'milp_strat': True,
                'hybrid_strat': False,
                'nsga_algo_strat': False,
                'min_store': 1,
                'find_min_store': False
            }

            # Run optimization
            self.update_state(state='PROGRESS', meta={'status': 'Running optimization'})
            results = PurchaseOptimizer.run_optimization(cards, sites, config)

            # Save results
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
            logger.error(f"Error during optimization: {str(e)}")
            self.update_state(state='FAILURE', meta={'status': f'Error: {str(e)}'})
            return {'status': 'Failed', 'error': str(e)}


@shared_task(name='app.tasks.optimization_tasks.cleanup_old_scans')
def cleanup_old_scans():
    print("Starting cleanup_old_scans task P")
    logger.info("Starting cleanup_old_scans task")
    from app import create_app
    app = create_app()
    with app.app_context():
        try:
            logger.info(f"Trying to clean up scans")
            # Logic to remove old scans and their results
            old_scans = Scan.query.filter(Scan.created_at < (datetime.now(timezone.utc) - timedelta(days=30))).all()
            logger.info(f"Scans received")
            for scan in old_scans:
                logger.info(f"Trying to delete scans {scan}")
                db.session.delete(scan)
            db.session.commit()
            logger.info(f"Cleanup completed")
            return {'status': 'Cleanup completed'}
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")
            return {'status': 'Failed', 'error': str(e)}
        
@shared_task
def test_task():
    logger.info("Test task is running")
    return {"status": "Test task completed"}