import logging
from flask import Blueprint, jsonify, request, current_app
from app.services.card_service import CardService
from app.tasks.optimization_tasks import start_scraping_task
from app.tasks.optimization_tasks import celery_app
from celery.result import AsyncResult
from celery.backends.base import DisabledBackend

logger = logging.getLogger(__name__)

# Defining Blueprint for Card Routes
card_routes = Blueprint("card_routes", __name__)

# Buylist Operations
@card_routes.route("/cards", methods=["GET"])
def get_cards():
    try:
        cards = CardService.get_user_buylist_cards()
        return jsonify([card.to_dict() for card in cards])
    except Exception as e:
        current_app.logger.error(f"Error fetching user cards: {str(e)}")
        return jsonify({"error": "Failed to fetch user cards"}), 500

@card_routes.route("/cards/<int:card_id>", methods=["PUT"])
def update_card(card_id):
    """
    Update a specific card in the user's buylist.
    """
    try:
        data = request.json

        # Delegate update to CardManager
        updated_card = CardService.update_user_buylist_card(card_id, data)
        if not updated_card:
            return jsonify({"error": "Card not found in user's buylist"}), 404

        # Return the updated card with all fields
        return jsonify(updated_card.to_dict()), 200

    except Exception as e:
        current_app.logger.error(f"Error updating card: {str(e)}")
        return jsonify({"error": "Failed to update card"}), 500

    
@card_routes.route("/cards", methods=["POST"])
def save_card():
    """
    Save a new card or update an existing card.
    """
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400

        required_fields = ["name"]
        if not all(field in data for field in required_fields):
            return jsonify({"error": "Missing required fields"}), 400

        # Standardize data fields
        card_data = {
            "name": data.get("name"),
            "set_name": data.get("set_name"),  # Changed from 'set'
            "language": data.get("language", "English"),
            "quantity": data.get("quantity", 0),
            "version": data.get("version", "Standard"),
            "foil": data.get("foil", False)
        }

        saved_card = CardService.save_card(**card_data)
        return jsonify(saved_card.to_dict()), 200
    except Exception as e:
        current_app.logger.error(f"Error saving card: {str(e)}")
        return jsonify({"error": "Failed to save card"}), 500
   
@card_routes.route("/fetch_card", methods=["GET"])
def fetch_card():
    card_name = request.args.get("name")
    set_code = request.args.get("set")
    language = request.args.get("language")
    version = request.args.get('version')

    if not card_name:
        return jsonify({"error": "Card name is required"}), 400

    card_data = CardService.fetch_card_data(card_name, set_code, language, version)
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
        task = AsyncResult(task_id, app=celery_app)
        logger.info(f"Task {task_id} task: {task}")  
        
        if task.state == 'PENDING':
            response = {
                'state': task.state,
                'status': 'Task is pending...'
            }
        elif task.state == 'FAILURE':
            response = {
                'state': task.state,
                'status': 'Task failed',
                'error': str(task.info)  # Get error info
            }
        elif task.state == 'SUCCESS':
            response = {
                'state': task.state,
                'result': task.get()  # Safely get the result
            }
        else:
            # Handle PROGRESS or other states
            response = {
                'state': task.state,
                'status': task.info.get('status', ''),
                'progress': task.info.get('progress', 0)
            }
        
        return jsonify(response), 200
        
    except Exception as e:
        logger.exception(f"Error checking task status: {str(e)}")
        return jsonify({
            'state': 'ERROR',
            'status': 'Error checking task status',
            'error': str(e)
        }), 500

@card_routes.route("/start_scraping", methods=["POST"])
def start_scraping():
    """Starts the scraping task."""
    data = request.json
    #current_app.logger.info("Received data: %s", data)

    site_ids = data.get("sites", [])
    card_list_from_frontend = data.get("card_list", [])
    strategy = data.get("strategy", "milp")
    min_store = data.get("min_store", 1)
    find_min_store = data.get("find_min_store", False)

    if not site_ids or not card_list_from_frontend:
        return jsonify({"error": "Missing site_ids or card_list"}), 400

    task = start_scraping_task.apply_async(
        args=[site_ids, card_list_from_frontend, strategy, min_store, find_min_store]
    )
    return jsonify({"task_id": task.id}), 202

# Set Operations
@card_routes.route("/sets", methods=["GET"])
def get_sets():
    try:
        sets = CardService.fetch_all_sets()
        return jsonify(sets)
    except Exception as e:
        current_app.logger.error(f"Error fetching sets: {str(e)}")
        return jsonify({"error": "Failed to fetch sets"}), 500

# Scan Operations
@card_routes.route("/scans/<int:scan_id>", methods=["GET"])
def get_scan_results(scan_id):
    try:
        scan = CardService.get_scan_results(scan_id)
        return jsonify(scan.to_dict())
    except Exception as e:
        current_app.logger.error(f"Error fetching scan results: {str(e)}")
        return jsonify({"error": "Failed to fetch scan results"}), 500

@card_routes.route("/scans", methods=["GET"])
def get_all_scans():
    limit = request.args.get("limit", 5, type=int)
    try:
        scans = CardService.get_all_scan_results(limit)
        return jsonify([scan.to_dict() for scan in scans])
    except Exception as e:
        current_app.logger.error(f"Error fetching scans: {str(e)}")
        return jsonify({"error": "Failed to fetch scans"}), 500
