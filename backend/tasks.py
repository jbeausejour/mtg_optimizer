#from optimization import run_optimization
from models import db, Card, Scan, ScanResult
import celery
from app import create_app

@celery.shared_task(bind=True)
def optimize_cards(self, card_list, sites):
    self.update_state(state='PROGRESS', meta={'status': 'Optimization in progress...'})
    
    app = create_app()
    with app.app_context():
        new_scan = Scan()
        db.session.add(new_scan)
        db.session.commit()

        config = {
            'filename': f'optimization_task_{self.request.id}',
            'log_level_file': 'INFO',
            'log_level_console': 'INFO',
            'special_site_flag': True,
            'milp_strat': True,
            'hybrid_strat': False,
            'nsga_algo_strat': False,
            'min_store': 1,
            'find_min_store': False
        }

        results= ""
        #results = run_optimization([card.name for card in card_list], config)

        for card in results['sites_results']:
            result = ScanResult(
                scan_id=new_scan.id,
                card_id=card['id'],
                site=card['site'],
                price=card['price']
            )
            db.session.add(result)
        
        db.session.commit()
    
    return {'status': 'Optimization completed', 'scan_id': new_scan.id}