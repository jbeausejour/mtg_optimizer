import logging
from flask import Blueprint, jsonify, request, current_app
from app.services.card_service import CardService
from app.services.scan_service import ScanService
from app.services.site_service import SiteService
from app.tasks.optimization_tasks import start_scraping_task
from app.tasks.optimization_tasks import celery_app
from celery.result import AsyncResult
from celery.backends.base import DisabledBackend
from app.services.optimization_service import OptimizationService

logger = logging.getLogger(__name__)

# Defining Blueprint for Card Routes
card_routes = Blueprint("card_routes", __name__)

# Card Operations
@card_routes.route("/cards", methods=["GET"])
def get_user_buylist_cards():
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
def update_user_buylist_card(card_id):
    """Update a specific card in the user's buylist."""
    try:
        data = request.json
        current_app.logger.info(f"Received update request for card {card_id}: {data}")

        updated_card = CardService.update_user_buylist_card(card_id, data)
        if not updated_card:
            return jsonify({"error": "Card not found in user's buylist"}), 404

        result = updated_card.to_dict()
        current_app.logger.info(f"Successfully updated card: {result}")
        return jsonify(result), 200

    except Exception as e:
        current_app.logger.error(f"Error updating card: {str(e)}")
        return jsonify({"error": f"Failed to update card: {str(e)}"}), 500

@card_routes.route("/cards", methods=["POST"])
def add_user_buylist_card():
    """Save a new card or update an existing card."""
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400

        # Standardize data fields
        card_data = {
            "name": data.get("name"),
            "set_name": data.get("set_name"),
            "set_code": data.get("set_code"),
            "language": data.get("language", "English"),
            "quantity": data.get("quantity", 0),
            "version": data.get("version", "Standard"),
            "foil": data.get("foil", False)
        }

        # Validate card data
        validation_errors = CardService.validate_card_data(card_data)
        if validation_errors:
            return jsonify({
                "error": "Validation failed",
                "details": validation_errors
            }), 400

        saved_card = CardService.add_user_buylist_card(**card_data)
        return jsonify(saved_card.to_dict()), 200
        
    except Exception as e:
        current_app.logger.error(f"Error saving card: {str(e)}")
        return jsonify({"error": "Failed to save card"}), 500

@card_routes.route("/fetch_card", methods=["GET"])
def fetch_scryfall_card():
    card_name = request.args.get("name")
    set_code = request.args.get("set_code")
    language = request.args.get("language")
    version = request.args.get('version')

    current_app.logger.info(f"Fetching card with params: name={card_name}, set_code={set_code}, lang={language}, ver={version}")

    if not card_name:
        return jsonify({
            "error": "Missing parameter",
            "details": "Card name is required"
        }), 400

    try:
        card_data = CardService.fetch_scryfall_card_data(card_name, set_code, language, version)
        if card_data is None:
            error_msg = f"Card not found: '{card_name}'"
            if set_code:
                error_msg += f" in set '{set_code}'"
            current_app.logger.warning(error_msg)
            
            return jsonify({
                "error": "Card not found",
                "details": error_msg,
                "params": {
                    "name": card_name,
                    "set_code": set_code,
                    "language": language,
                    "version": version
                },
                "scryfall": {
                    "name": None,
                    "set": None,  # makesure this is supposed to be set and not set_code
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
        
    except Exception as e:
        error_msg = f"Error fetching card data: {str(e)}"
        current_app.logger.error(error_msg)
        return jsonify({
            "error": "API Error",
            "details": error_msg,
            "params": {
                "name": card_name,
                "set": set_code,
                "language": language,
                "version": version
            }
        }), 500
 
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

@card_routes.route("/save_set_selection", methods=["POST"])
def save_set_selection():
    """Save the selected set for a card"""
    try:
        data = request.json
        set_code = data.get('set_code')
        if not set_code:
            return jsonify({"error": "Set code is required"}), 400
        
        # Store the selected set (you might want to save this to your database)
        # For now, just return success
        return jsonify({"message": f"Set {set_code} selected successfully"}), 200
    except Exception as e:
        current_app.logger.error(f"Error saving set selection: {str(e)}")
        return jsonify({"error": "Failed to save set selection"}), 500

# Scan Operations
@card_routes.route("/scans/<int:scan_id>", methods=["GET"])
def get_scan_results(scan_id):
    try:
        scan = ScanService.get_scan_results(scan_id)
        if not scan:
            return jsonify({"error": "Scan not found"}), 404
            
        return jsonify(scan.to_dict())
    except Exception as e:
        current_app.logger.error(f"Error fetching scan results: {str(e)}")
        return jsonify({"error": "Failed to fetch scan results"}), 500

@card_routes.route("/scans", methods=["GET"])
def get_all_scans():
    limit = request.args.get("limit", 5, type=int)
    try:
        scans = ScanService.get_all_scan_results(limit)
        return jsonify([{
            'id': scan.id,
            'created_at': scan.created_at.isoformat(),
            'cards_scraped': len(scan.scan_results) if scan.scan_results else 0,
            'sites_scraped': len(set(r.site_id for r in scan.scan_results)) if scan.scan_results else 0
        } for scan in scans])
    except Exception as e:
        current_app.logger.error(f"Error fetching scans: {str(e)}")
        return jsonify({"error": "Failed to fetch scans"}), 500

@card_routes.route("/scans/", methods=["GET"])
def get_scan_history():
    """Get scan history without optimization results"""
    scans = ScanService.get_all_scan_results()
    return jsonify([
        {
            'id': scan.id,
            'created_at': scan.created_at.isoformat(),
            'cards_scraped': len(scan.scan_results),
            'sites_scraped': len(set(r.site_id for r in scan.scan_results)),
            'scan_results': [r.to_dict() for r in scan.scan_results]
        }
        for scan in scans
    ])

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
            return jsonify({
                "status": "warning",
                "message": "No data provided for update"
            }), 400

        updated_site = SiteService.update_site(site_id, data)
        if not updated_site:
            return jsonify({
                "status": "info",
                "message": "No changes were needed - site data is already up to date"
            }), 200

        return jsonify({
            "status": "success",
            "message": "Site updated successfully",
            "site": updated_site.to_dict(),
        }), 200

    except ValueError as ve:
        return jsonify({
            "status": "warning",
            "message": str(ve)
        }), 400
    except Exception as e:
        current_app.logger.error(f"Unexpected error: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "An unexpected error occurred while updating the site"
        }), 500

# Optimization Operations
@card_routes.route('/results', methods=['GET'])
def get_optimization_results():
    """Get recent optimization results"""
    limit = request.args.get('limit', 5, type=int)
    results = OptimizationService.get_optimization_results(limit)
    
    response = []
    for scan, opt_result in results:
        if opt_result:  # Only include results that have optimization data
            response.append({
                'id': scan.id,
                'created_at': opt_result.created_at.isoformat(),
                'solutions': opt_result.solutions,
                'status': opt_result.status,
                'message': opt_result.message,
                'sites_scraped': opt_result.sites_scraped,
                'cards_scraped': opt_result.cards_scraped,
                'errors': opt_result.errors
            })
    
    return jsonify(response)

# Fix duplicate function name
@card_routes.route('/results/<int:scan_id>', methods=['GET'])
def get_scan_optimization_result(scan_id):
    """Get optimization results for a specific scan"""    
    opt_results = OptimizationService.get_optimization_results_by_scan(scan_id)
    if not opt_results or len(opt_results) == 0:
        return jsonify({'error': 'No optimization results found'}), 404
    
    opt_result = opt_results[0]  # Get the first/latest result
    
    response = {
        'id': scan_id,
        'created_at': opt_result.created_at.isoformat(),
        'solutions': opt_result.solutions,
        'status': opt_result.status,
        'message': opt_result.message,
        'sites_scraped': opt_result.sites_scraped,
        'cards_scraped': opt_result.cards_scraped,
        'errors': opt_result.errors
    }
    
    return jsonify(response)

@card_routes.route('/results/latest', methods=['GET'])
def get_latest_optimization_results():
        
    opt_result = OptimizationService.get_latest_optimization()
    if not opt_result:
        return jsonify({'error': 'No optimization results found'}), 404
    
    response = {
        'id': opt_result.scan_id,
        'created_at': opt_result.created_at.isoformat(),
        'optimization': opt_result.to_dict()
    }
    
    return jsonify(response)