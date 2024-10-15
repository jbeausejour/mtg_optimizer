import logging
from flask import Blueprint, jsonify, request
from app.services.card_manager import CardManager

logger = logging.getLogger(__name__)

# Defining Blueprint for Card Routes
card_routes = Blueprint("card_routes", __name__)

# Buylist Operations
@card_routes.route("/cards", methods=["GET"])
def get_cards():
    try:
        cards = CardManager.get_user_buylist_cards()
        return jsonify([card.to_dict() for card in cards])
    except Exception as e:
        logger.error(f"Error fetching user cards: {str(e)}")
        return jsonify({"error": "Failed to fetch user cards"}), 500

@card_routes.route("/fetch_card", methods=["GET"])
def fetch_card():
    card_name = request.args.get("name")
    set_code = request.args.get("set")
    language = request.args.get("language")

    if not card_name:
        return jsonify({"error": "Card name is required"}), 400

    card_data = CardManager.fetch_card_data(card_name, set_code, language)
    if card_data is None:
        return jsonify({
            "scryfall": {
                "name": None,
                "set": None,
                "type": None,
                "rarity": None,
                "mana_cost": None,
                "text": None,
                "flavor": None,
                "power": None,
                "toughness": None,
                "loyalty": None
            },
            "scan_timestamp": None
        }), 404

    if isinstance(card_data, dict) and 'scryfall' in card_data:
        card_data['scryfall'] = {key: value for key, value in card_data['scryfall'].items() if value is not None}

    return jsonify(card_data)


# Set Operations
@card_routes.route("/sets", methods=["GET"])
def get_sets():
    try:
        sets = CardManager.fetch_all_sets()
        return jsonify(sets)
    except Exception as e:
        logger.error(f"Error fetching sets: {str(e)}")
        return jsonify({"error": "Failed to fetch sets"}), 500

# Scan Operations
@card_routes.route("/scans/<int:scan_id>", methods=["GET"])
def get_scan_results(scan_id):
    try:
        scan = CardManager.get_scan_results(scan_id)
        return jsonify(scan.to_dict())
    except Exception as e:
        logger.error(f"Error fetching scan results: {str(e)}")
        return jsonify({"error": "Failed to fetch scan results"}), 500

@card_routes.route("/scans", methods=["GET"])
def get_all_scans():
    limit = request.args.get("limit", 5, type=int)
    try:
        scans = CardManager.get_all_scan_results(limit)
        return jsonify([scan.to_dict() for scan in scans])
    except Exception as e:
        logger.error(f"Error fetching scans: {str(e)}")
        return jsonify({"error": "Failed to fetch scans"}), 500
