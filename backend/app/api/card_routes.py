from flask import Blueprint, jsonify, request
from app.services.card_service import CardDataManager
import logging

logger = logging.getLogger(__name__)

card_routes = Blueprint('card_routes', __name__)

@card_routes.route('/cards', methods=['GET'])
def get_cards():
    cards = CardDataManager.get_all_user_buylist_cards()
    return jsonify([card.to_dict() for card in cards])

@card_routes.route('/card_suggestions', methods=['GET'])
def get_card_suggestions():
    query = request.args.get('query', '')
    suggestions = CardDataManager.get_card_suggestions(query)
    return jsonify(suggestions)

@card_routes.route('/card_versions', methods=['GET'])
def get_card_versions():
    card_name = request.args.get('name')
    if not card_name:
        return jsonify({'error': 'Card name is required'}), 400
    
    versions = CardDataManager.get_scryfall_card_versions(card_name)
    return jsonify(versions)

@card_routes.route('/fetch_card', methods=['GET'])
def fetch_card():
    card_name = request.args.get('name')
    set_code = request.args.get('set')
    language = request.args.get('language')
    version = request.args.get('version')

    if not card_name:
        return jsonify({'error': 'Card name is required'}), 400

    try:
        card_data = CardDataManager.fetch_card_data(card_name, set_code, language, version)
        if card_data is None:
            return jsonify({'error': 'Card not found'}), 404
        return jsonify(card_data)
    except Exception as e:
        logger.error(f"Error fetching card data: {str(e)}")
        return jsonify({'error': 'Failed to fetch card data'}), 500

@card_routes.route('/sets', methods=['GET'])
def get_sets():
    sets_data = CardDataManager.get_all_sets_from_scryfall()	   
    return jsonify([set_data.to_dict() for set_data in sets_data])
