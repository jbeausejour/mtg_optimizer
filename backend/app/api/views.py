from flask import Blueprint, jsonify, request
from app.tasks.optimization_tasks import optimize_cards
from app.services.card_service import get_all_cards, get_card_versions, fetch_card_data
from app.services.site_service import get_all_sites
from app.services.scan_service import get_scan_results, get_all_scan_results
from app.utils.data_fetcher import DataFetcher
import logging
import asyncio


logger = logging.getLogger(__name__)
views = Blueprint('views', __name__)

@views.route('/cards', methods=['GET'])
def get_cards():
    print("cards route hit!")
    cards = get_all_cards()
    #print(cards)
    return jsonify([card.to_dict() for card in cards])

@views.route('/sites', methods=['GET'])
def get_site_list():
    print("sites route hit!")
    sites = get_all_sites()
    return jsonify([site.to_dict() for site in sites])

@views.route('/card_versions', methods=['GET'])
def get_card_versions_route():
    logger.info("card_versions route hit!")
    print("card_versions route hit!")
    card_name = request.args.get('name')
    if not card_name:
        return jsonify({'error': 'Card name is required'}), 400
    
    versions = get_card_versions(card_name)
    return jsonify(versions)

@views.route('/fetch_card', methods=['GET'])
def fetch_card():
    logger.info("fetch_card route hit!")
    card_name = request.args.get('name')
    set_code = request.args.get('set')
    language = request.args.get('language')
    version = request.args.get('version')

    if not card_name:
        return jsonify({'error': 'Card name is required'}), 400

    try:
        card_data = fetch_card_data(card_name, set_code, language, version)
        return jsonify(card_data)
    except Exception as e:
        logger.error(f"Error fetching card data: {str(e)}")
        return jsonify({'error': 'Failed to fetch card data'}), 500

@views.route('/optimize', methods=['POST'])
def optimize():
    sites = request.json.get('sites', [])
    card_list = get_all_cards()  # Assuming this function exists in your services

    # Run the optimization synchronously
    result = optimize_cards(card_list, sites)

    # Return the result immediately
    return jsonify(result), 200

@views.route('/results/<int:scan_id>', methods=['GET'])
def get_results(scan_id):
    scan = get_scan_results(scan_id)
    return jsonify(scan.to_dict())

@views.route('/scans', methods=['GET']) 
def get_scans():
    scans = get_all_scan_results()
    return jsonify([scan.to_dict() for scan in scans])

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