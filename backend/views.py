from flask import Blueprint, jsonify, request
from services import get_all_cards, get_all_sites, get_card_versions, fetch_card_data
import logging

logger = logging.getLogger(__name__)
views = Blueprint('views', __name__)

@views.route('/cards', methods=['GET'])
def get_cards():
    cards = get_all_cards()
    return jsonify([card.to_dict() for card in cards])

@views.route('/sites', methods=['GET'])
def get_site_list():
    sites = get_all_sites()
    return jsonify([site.to_dict() for site in sites])

@views.route('/card_versions', methods=['GET'])
def get_card_versions_route():
    card_name = request.args.get('name')
    if not card_name:
        return jsonify({'error': 'Card name is required'}), 400
    
    versions = get_card_versions(card_name)
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
        card_data = fetch_card_data(card_name, set_code, language, version)
        return jsonify(card_data)
    except Exception as e:
        logger.error(f"Error fetching card data: {str(e)}")
        return jsonify({'error': 'Failed to fetch card data'}), 500

@views.route('/optimize', methods=['POST'])
def optimize():
    sites = request.json.get('sites', [])
    # Implement your optimization logic here
    # This is a placeholder response
    return jsonify({'message': 'Optimization completed', 'optimized_sites': sites})