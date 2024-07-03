#from optimization import run_optimization
from app.models.scan import Scan, ScanResult
from app import create_app, db

#@celery.shared_task(bind=True)
def optimize_cards(card_list, sites):
    app = create_app()
    with app.app_context():
        new_scan = Scan()
        db.session.add(new_scan)
        db.session.commit()

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

        results = ""
        # Uncomment this when you have the run_optimization function ready
        # results = run_optimization([card.name for card in card_list], config)

        for card in results.get('sites_results', []):
            result = ScanResult(
                scan_id=new_scan.id,
                card_id=card['id'],
                site=card['site'],
                price=card['price']
            )
            db.session.add(result)
        
        db.session.commit()
    
    return {'status': 'Optimization completed', 'scan_id': new_scan.id}