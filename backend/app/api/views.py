from flask import Blueprint, jsonify, request
from app.tasks.optimization_tasks import optimize_cards
from app.services.card_service import CardService
from app.services.site_service import SiteService
from app.services.scan_service import ScanService
from app.utils.data_fetcher import DataFetcher
from app.utils.load_initial_data import load_all_data, truncate_tables
import logging
import asyncio


logger = logging.getLogger(__name__)
views = Blueprint('views', __name__)

@views.route('/cards', methods=['GET'])
def get_cards():
    cards = CardService.get_all_cards()
    #print(cards)
    return jsonify([card.to_dict() for card in cards])

@views.route('/sites', methods=['GET'])
def get_site_list():
    sites = SiteService.get_all_sites()
    return jsonify([site.to_dict() for site in sites])

@views.route('/sets', methods=['GET'])
def get_sets():
    sets_data = CardService.get_all_sets()
    return jsonify([set_data.to_dict() for set_data in sets_data])

@views.route('/scans', methods=['GET']) 
def get_scans():
    scans = ScanService.get_all_scan_results()
    return jsonify([scan.to_dict() for scan in scans])

@views.route('/card_versions', methods=['GET'])
def get_card_versions_route():
    card_name = request.args.get('name')
    if not card_name:
        return jsonify({'error': 'Card name is required'}), 400
    
    versions = CardService.get_card_versions(card_name)
    return jsonify(versions)

@views.route('/fetch_card', methods=['GET'])
def fetch_card():
    card_name = request.args.get('name')
    set_code = request.args.get('set')
    language = request.args.get('language')
    version = request.args.get('version')

    if not card_name:
        return jsonify({'error': 'Card name is required'}), 400

    try:
        card_data = CardService.fetch_card_data(card_name, set_code, language, version)
        return jsonify(card_data)
    except Exception as e:
        logger.error(f"Error fetching card data: {str(e)}")
        return jsonify({'error': 'Failed to fetch card data'}), 500

@views.route('/optimize', methods=['POST'])
def optimize():
    sites = request.json.get('sites', [])
    card_list = CardService.get_all_cards()

    try:
        # Convert Card_list objects to dictionaries
        card_list_dicts = [card.to_dict() for card in card_list]
        
        # Run the optimization as a Celery task
        task = optimize_cards.delay(card_list_dicts, sites)

        return jsonify({
            'status': 'Optimization task started',
            'task_id': task.id
        }), 202  # 202 Accepted
    except Exception as e:
        logger.error(f"Error starting optimization task: {str(e)}")
        return jsonify({'error': 'Failed to start optimization task'}), 500

@views.route('/optimization_status/<task_id>', methods=['GET'])
def optimization_status(task_id):
    task = optimize_cards.AsyncResult(task_id)
    if task.state == 'PENDING':
        response = {
            'state': task.state,
            'status': 'Optimization task is pending...'
        }
    elif task.state != 'FAILURE':
        response = {
            'state': task.state,
            'status': task.info.get('status', '')
        }
        if 'result' in task.info:
            response['result'] = task.info['result']
    else:
        response = {
            'state': task.state,
            'status': str(task.info)
        }
    return jsonify(response)

@views.route('/results/<int:scan_id>', methods=['GET'])
def get_results(scan_id):
    scan = ScanService.get_scan_results(scan_id)
    return jsonify(scan.to_dict())

@views.route('/update_card_data', methods=['POST'])
def update_card_data():
    try:
        # Run the asynchronous update_all_cards method
        asyncio.run(DataFetcher.update_all_cards())
        
        return jsonify({
            "status": "success",
            "message": "Card data update process has been initiated."
        }), 202  # 202 Accepted
    except Exception as e:
        logger.error(f"Error updating card data: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"An error occurred: {str(e)}"
        }), 500

@views.route('/load-data', methods=['POST'])
def load_data():
    try:
        logger.info("Starting data truncation")
        truncate_tables()
        logger.info("Data truncation completed")
        
        logger.info("Starting data loading")
        load_all_data()
        logger.info("Data loading completed successfully")
        
        return jsonify({"message": "Data loaded successfully"}), 200
    except Exception as e:
        logger.error(f"Error during data loading: {str(e)}")
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500