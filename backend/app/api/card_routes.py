import logging
from flask import Blueprint, jsonify, request, current_app
from app.services.card_manager import CardManager
from app.tasks.optimization_tasks import start_scraping_task
from celery.result import AsyncResult

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
        current_app.logger.error(f"Error fetching user cards: {str(e)}")
        return jsonify({"error": "Failed to fetch user cards"}), 500

@card_routes.route("/fetch_card", methods=["GET"])
def fetch_card():
    card_name = request.args.get("name")
    set_code = request.args.get("set")
    language = request.args.get("language")
    version = request.args.get('version')

    if not card_name:
        return jsonify({"error": "Card name is required"}), 400

    card_data = CardManager.fetch_card_data(card_name, set_code, language, version)
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

    return jsonify(card_data)

# Optimization Operations (Merged from optimization_routes)
@card_routes.route("/task_status/<task_id>", methods=["GET"])
def task_status(task_id):
    try:
        result = AsyncResult(task_id)
        response = {
            'state': result.state,
            'status': result.info.get('status', '') if result.info else None,
        }
        if result.state == 'FAILURE':
            response['error'] = str(result.info)  # Convert the error message to a string to make it JSON serializable
        return jsonify(response)
    except Exception as e:
        # Properly serialize the exception message before returning
        return jsonify({'error': str(e)}), 500


@card_routes.route("/start_scraping", methods=["POST"])
def start_scraping():
    """Starts the scraping task."""
    data = request.json
    current_app.logger.info("Received data: %s", data)

    site_ids = data.get("sites", [])
    card_list = data.get("card_list", [])
    strategy = data.get("strategy", "milp")
    min_store = data.get("min_store", 1)
    find_min_store = data.get("find_min_store", False)

    if not site_ids or not card_list:
        return jsonify({"error": "Missing site_ids or card_list"}), 400

    task = start_scraping_task.apply_async(
        args=[site_ids, card_list, strategy, min_store, find_min_store]
    )
    return jsonify({"task_id": task.id}), 202

# Set Operations
@card_routes.route("/sets", methods=["GET"])
def get_sets():
    try:
        sets = CardManager.fetch_all_sets()
        return jsonify(sets)
    except Exception as e:
        current_app.logger.error(f"Error fetching sets: {str(e)}")
        return jsonify({"error": "Failed to fetch sets"}), 500

# Scan Operations
@card_routes.route("/scans/<int:scan_id>", methods=["GET"])
def get_scan_results(scan_id):
    try:
        scan = CardManager.get_scan_results(scan_id)
        return jsonify(scan.to_dict())
    except Exception as e:
        current_app.logger.error(f"Error fetching scan results: {str(e)}")
        return jsonify({"error": "Failed to fetch scan results"}), 500

@card_routes.route("/scans", methods=["GET"])
def get_all_scans():
    limit = request.args.get("limit", 5, type=int)
    try:
        scans = CardManager.get_all_scan_results(limit)
        return jsonify([scan.to_dict() for scan in scans])
    except Exception as e:
        current_app.logger.error(f"Error fetching scans: {str(e)}")
        return jsonify({"error": "Failed to fetch scans"}), 500
