import logging
from flask import Blueprint, jsonify, request, current_app
from app.services.card_service import CardService
from app.services.scan_service import ScanService
from app.services.site_service import SiteService
from app.tasks.optimization_tasks import start_scraping_task
from app.tasks.optimization_tasks import celery_app
from celery.result import AsyncResult
from celery.backends.base import DisabledBackend

logger = logging.getLogger(__name__)

# Defining Blueprint for Card Routes
card_routes = Blueprint("card_routes", __name__)

# Card Operations
@card_routes.route("/cards", methods=["GET"])
def get_cards():
    """
    Get all the cards in the user's buylist.
    """
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
 
@card_routes.route("/card_suggestions", methods=["GET"])
def get_card_suggestions():
    query = request.args.get("query", "")
    suggestions = CardService.get_card_suggestions(query)
    return jsonify(suggestions)

# Task Operations
@card_routes.route("/task_status/<task_id>", methods=["GET"])
def task_status(task_id):
    try:
        task = AsyncResult(task_id, app=celery_app)
        
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
        
        logger.info(f"Task {task_id} response: {response}")  
        return jsonify(response), 200
        
    except Exception as e:
        logger.exception(f"Error checking task status: {str(e)}")
        return jsonify({
            'state': 'ERROR',
            'status': 'Error checking task status',
            'error': str(e)
        }), 500

# Optimization Operations
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
@card_routes.route("/results/<int:scan_id>", methods=["GET"])
def get_scan_results(scan_id):
    try:
        scan = ScanService.get_scan_results(scan_id)
        if not scan:
            return jsonify({"error": "Scan not found"}), 404
            
        return jsonify(scan.to_dict())
    except Exception as e:
        current_app.logger.error(f"Error fetching scan results: {str(e)}")
        return jsonify({"error": "Failed to fetch scan results"}), 500

@card_routes.route("/results", methods=["GET"])
def get_all_scans():
    limit = request.args.get("limit", 5, type=int)
    try:
        scans = ScanService.get_all_scan_results(limit)
        return jsonify([scan.to_dict() for scan in scans])
    except Exception as e:
        current_app.logger.error(f"Error fetching scans: {str(e)}")
        return jsonify({"error": "Failed to fetch scans"}), 500

# Site Operations
@card_routes.route("/sites", methods=["GET"])
def get_sites():
    sites = SiteService.get_all_sites()
    return jsonify([site.to_dict() for site in sites])

@card_routes.route("/sites", methods=["POST"])
def add_site():
    try:
        data = request.json
        new_site = SiteService.add_site(data)
        return jsonify(new_site.to_dict()), 201
    except Exception as e:
        current_app.logger.error(f"Error adding site: {str(e)}")
        return jsonify({"error": "Failed to add site"}), 500

@card_routes.route("/sites/<int:site_id>", methods=["PUT"])
def update_site(site_id):
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400

        updated_site = SiteService.update_site(site_id, data)
        return jsonify({
            "message": "Site updated successfully",
            "site": updated_site.to_dict(),
        }), 200
    except ValueError as ve:
        current_app.logger.warning(f"Validation error updating site: {str(ve)}")
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        current_app.logger.error(f"Unexpected error: {str(e)}")
        return jsonify({"error": "An unexpected error occurred"}), 500
