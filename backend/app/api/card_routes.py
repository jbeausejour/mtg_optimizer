import logging
import logging
from flask import Blueprint, request, jsonify

from app.services.card_service import CardService
from app.services.optimization_service import OptimizationService
from app.services.scan_service import ScanService
from app.services.site_service import SiteService
from app.tasks.optimization_tasks import celery_app, start_scraping_task
from celery.backends.base import DisabledBackend
from celery.result import AsyncResult
from flask import Blueprint, current_app, jsonify, request

logger = logging.getLogger(__name__)

# Defining Blueprint for Card Routes
card_routes = Blueprint("card_routes", __name__)


############################################################################################################
# Buylist Operations
############################################################################################################
@card_routes.route("/buylists", methods=["GET"])
def get_buylists():
    """Get all saved buylists for a specific user."""
    try:
        user_id = request.args.get("user_id")
        if not user_id:
            logger.error("User ID is missing in the request")
            return jsonify({"error": "User ID is required"}), 400

        buylists = CardService.get_all_buylists(user_id)
        logger.info(f"Found {len(buylists)} buylists for user {user_id}")
        # logger.info(f"Found {len(buylists)} buylists for user {user_id}: data={buylists}")
        return jsonify(buylists)
    except Exception as e:
        logger.error(f"Error fetching buylists: {str(e)}")
        return jsonify({"error": "Failed to fetch buylists"}), 500


@card_routes.route("/buylists", methods=["POST"])
def create_buylist():
    """
    Create a new buylist.
    """
    try:
        data = request.json
        name = data.get("name", "Untitled Buylist")
        user_id = data.get("user_id")

        if not user_id:
            return jsonify({"error": "User ID is required"}), 400

        logger.info(f"Creating new buylist '{name}' for user {user_id}")
        new_buylist = CardService.create_buylist(name=name, user_id=user_id)
        return jsonify(new_buylist.to_dict()), 201

    except Exception as e:
        logger.error(f"Error creating buylist: {str(e)}")
        return jsonify({"error": "Failed to create buylist"}), 500


@card_routes.route("/buylists/<int:id>", methods=["GET"])
def load_buylist(id=None):
    """Load a saved buylist by ID or all buylists' cards if ID is None."""
    try:
        user_id = request.args.get("user_id")
        if not user_id:
            return jsonify({"error": "User ID is required"}), 400

        if id:
            logger.info(f"Loading buylist {id} for user {user_id}")
            buylist_cards = CardService.get_buylist_cards_by_id(id)
            logger.info(f"Loaded {len(buylist_cards)} cards for buylist {id}")
        else:
            logger.info(f"Loading all buylist cards for user {user_id}")
            buylist_cards = CardService.get_all_user_buylist_cards(user_id)
            logger.info(f"Loaded all {len(buylist_cards)} cards for user {user_id}")

        return jsonify([card.to_dict() for card in buylist_cards]), 200

    except Exception as e:
        logger.error(f"Error loading buylist: {str(e)}")
        return jsonify({"error": "Failed to load buylist"}), 500


@card_routes.route("/buylists/<int:id>", methods=["DELETE"])
def delete_buylist(id):
    """
    Delete a buylist by its ID.
    """
    try:
        user_id = request.args.get("user_id")
        if not user_id:
            return jsonify({"error": "User ID is required"}), 400

        # Call the service to delete the buylist
        deleted = CardService.delete_buylist(id, user_id)

        if deleted:
            return jsonify({"message": "Buylist deleted successfully"}), 200
        else:
            return jsonify({"error": "Buylist not found or could not be deleted"}), 404
    except Exception as e:
        logger.error(f"Error deleting buylist {id}: {str(e)}")
        return jsonify({"error": "Failed to delete buylist"}), 500


@card_routes.route("/buylists/<int:id>/cards", methods=["POST"])
def add_cards_to_buylist(id):
    """
    Add cards to an existing buylist.
    """
    try:
        data = request.json
        user_id = data.get("user_id")
        cards = data.get("cards", [])

        if not user_id:
            return jsonify({"error": "User ID is required"}), 400

        if not cards:
            return jsonify({"error": "No cards provided"}), 400

        logger.info(f"Adding cards to buylist {id} for user {user_id}")
        updated_buylist = CardService.add_card_to_buylist(id, user_id, cards)
        return jsonify(updated_buylist.to_dict()), 201

    except Exception as e:
        logger.error(f"Error adding cards to buylist {id}: {str(e)}")
        return jsonify({"error": "Failed to add cards to buylist"}), 500


@card_routes.route("/buylists/<int:id>/rename", methods=["PUT"])
def rename_buylist(id):
    """
    Rename an existing buylist without affecting its cards.
    """
    try:
        data = request.json
        new_name = data.get("name")
        user_id = data.get("user_id")

        if not user_id or not new_name:
            return jsonify({"error": "User ID and new buylist name are required"}), 400

        updated_buylist = CardService.update_user_buylist_name(id, user_id, new_name)
        return jsonify(updated_buylist.to_dict()), 200

    except Exception as e:
        logger.error(f"Error renaming buylist {id}: {str(e)}")
        return jsonify({"error": "Failed to rename buylist"}), 500


@card_routes.route("/buylists/top", methods=["GET"])
def get_top_buylists():
    """Get the top 3 buylists for a specific user."""
    try:
        user_id = request.args.get("user_id")
        if not user_id:
            logger.error("User ID is missing in the request")
            return jsonify({"error": "User ID is required"}), 400

        buylists = CardService.get_top_buylists(user_id)
        logger.info(f"Found top buylists for user {user_id}: data={buylists}")
        return jsonify(buylists)
    except Exception as e:
        logger.error(f"Error fetching top buylists: {str(e)}")
        return jsonify({"error": "Failed to fetch top buylists"}), 500


############################################################################################################
# Buylist Card Operations
############################################################################################################


@card_routes.route("/buylist/cards", methods=["DELETE"])
def delete_cards():
    """
    Delete specific cards from a buylist.

    Expects a JSON payload with:
    - id: The ID of the buylist
    - user_id: The ID of the user
    - cards: A list of cards to delete
    """
    try:
        data = request.json
        id = data.get("id")
        user_id = data.get("user_id")
        cards = data.get("cards")

        if not id or not user_id or not cards:
            return jsonify({"error": "Buylist ID, user ID, and cards are required"}), 400

        deleted_cards = []
        for card in cards:
            card_name = card.get("name")
            quantity = card.get("quantity", 1)

            # Delete the card
            deleted = CardService.delete_card_from_buylist(
                id=id, card_name=card_name, quantity=quantity, user_id=user_id
            )
            if deleted:
                deleted_cards.append({"name": card_name, "quantity": quantity})
            else:
                logger.warning(f"Card not found or could not be deleted: {card_name}")

        return jsonify({"deletedCards": deleted_cards}), 200

    except Exception as e:
        logger.error(f"Error deleting cards: {str(e)}")
        return jsonify({"error": "Failed to delete cards"}), 500


@card_routes.route("/buylist/cards/import", methods=["POST"])
def import_cards_to_buylist():
    """Import cards into a buylist from a text input."""
    try:
        data = request.json
        id = data.get("id")
        cards = data.get("cards", [])
        user_id = data.get("user_id")

        if not user_id:
            logger.error("User ID is missing in the request")
            return jsonify({"error": "User ID is required"}), 400

        if not id or not cards:
            return jsonify({"error": "Buylist ID and cards are required"}), 400

        added_cards = []
        not_found_cards = []

        for card in cards:
            card_name = card.get("name")
            quantity = card.get("quantity", 1)

            # Validate card existence (e.g., via Scryfall API)
            if CardService.is_valid_card_name(card_name):
                CardService.add_user_buylist_card(
                    name=card_name,
                    quantity=quantity,
                    buylist_id=id,
                    user_id=user_id,
                )
                logger.info(f"card {card_name} found")
                added_cards.append({"name": card_name, "quantity": quantity})
            else:
                logger.info(f"card {card_name} not found")
                not_found_cards.append({"name": card_name})

        return jsonify({"addedCards": added_cards, "notFoundCards": not_found_cards}), 200

    except Exception as e:
        logger.error(f"Error importing cards: {str(e)}")
        return jsonify({"error": "Failed to import cards"}), 500


@card_routes.route("/buylist/cards/<int:card_id>", methods=["PUT"])
def update_user_buylist_card(card_id):
    """Update a specific card in the user's buylist."""
    try:
        data = request.json
        user_id = data.get("user_id")
        id = data.get("id")  # Ensure buylist id is provided

        if not user_id or not id:
            return jsonify({"error": "User ID and Buylist ID are required"}), 400

        logger.info(f"Received update request for card {card_id}: {data}")

        updated_card = CardService.update_user_buylist_card(card_id, user_id, data)
        if not updated_card:
            return jsonify({"error": "Card not found in user's buylist"}), 404

        result = updated_card.to_dict()
        logger.info(f"Successfully updated card: {result}")
        return jsonify(result), 200

    except Exception as e:
        logger.error(f"Error updating card: {str(e)}")
        return jsonify({"error": f"Failed to update card: {str(e)}"}), 500


############################################################################################################
# Card Operations
############################################################################################################


@card_routes.route("/fetch_card", methods=["GET"])
def fetch_scryfall_card():

    card_name = request.args.get("name")
    set_code = request.args.get("set_code")
    language = request.args.get("language")
    version = request.args.get("version")

    logger.info(f"Fetching card with params: name={card_name}, set_code={set_code}, lang={language}, ver={version}")

    if not card_name:
        return jsonify({"error": "Missing parameter", "details": "Card name is required"}), 400

    try:
        card_data = CardService.fetch_scryfall_card_data(card_name, set_code, language, version)
        if card_data is None:
            error_msg = f"Card not found: '{card_name}'"
            if set_code:
                error_msg += f" in set '{set_code}'"
            logger.warning(error_msg)

            return (
                jsonify(
                    {
                        "error": "Card not found",
                        "details": error_msg,
                        "params": {"name": card_name, "set_code": set_code, "language": language, "version": version},
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
                            "loyalty": None,
                        },
                        "scan_timestamp": None,
                    }
                ),
                404,
            )

        return jsonify(card_data)

    except Exception as e:
        error_msg = f"Error fetching card data: {str(e)}"
        logger.error(error_msg)
        return (
            jsonify(
                {
                    "error": "API Error",
                    "details": error_msg,
                    "params": {"name": card_name, "set": set_code, "language": language, "version": version},
                }
            ),
            500,
        )


@card_routes.route("/card_suggestions", methods=["GET"])
def get_card_suggestions():
    query = request.args.get("query", "")
    suggestions = CardService.get_card_suggestions(query)
    return jsonify(suggestions)


############################################################################################################
# Task Operations
############################################################################################################
@card_routes.route("/task_status/<task_id>", methods=["GET"])
def task_status(task_id):
    try:
        task = AsyncResult(task_id, app=celery_app)
        if task.state == "PENDING":
            response = {"state": task.state, "status": "Task is pending..."}
        elif task.state == "FAILURE":
            response = {"state": task.state, "status": "Task failed", "error": str(task.info)}  # Get error info
        elif task.state == "SUCCESS":
            response = {"state": task.state, "result": task.get()}
        else:
            # Handle PROGRESS or other states
            response = {
                "state": task.state,
                "status": task.info.get("status", ""),
                "progress": task.info.get("progress", 0),
            }

        logger.info(
            f"Task {task_id} state: {task.state}, status: {task.info.get('status', '')}, progress: {task.info.get('progress', 0)}"
        )
        return jsonify(response), 200

    except Exception as e:
        logger.exception(f"Error checking task status: {str(e)}")
        return jsonify({"state": "ERROR", "status": "Error checking task status", "error": str(e)}), 500


############################################################################################################
# Optimization Operations
############################################################################################################
@card_routes.route("/start_scraping", methods=["POST"])
def start_scraping():
    """Starts the scraping task."""
    data = request.json
    # logger.info("Received data: %s", data)

    site_ids = data.get("sites", [])
    card_list_from_frontend = data.get("card_list", [])
    strategy = data.get("strategy", "milp")
    min_store = data.get("min_store", 1)
    find_min_store = data.get("find_min_store", False)
    min_age_seconds = data.get("min_age_seconds", 1800)
    buylist_id = data.get("buylist_id", None)

    if not site_ids or not card_list_from_frontend:
        return jsonify({"error": "Missing site_ids or card_list"}), 400

    task = start_scraping_task.apply_async(
        args=[site_ids, card_list_from_frontend, strategy, min_store, find_min_store, min_age_seconds, buylist_id]
    )
    return jsonify({"task_id": task.id}), 202


@card_routes.route("/purchase_order", methods=["POST"])
def generate_purchase_links():
    try:
        data = request.json
        purchase_data = data.get("purchase_data", [])

        active_sites = {site.id: site for site in SiteService.get_all_sites()}
        results = CardService.generate_purchase_links(purchase_data, active_sites)
        # logger.info(f"return data: {results}")
        return jsonify(results), 200

    except Exception as e:
        logger.error(f"Error generating purchase links: {str(e)}")
        return jsonify({"error": "Failed to generate purchase links"}), 500


############################################################################################################
# Set Operations
############################################################################################################
@card_routes.route("/sets", methods=["GET"])
def get_sets():
    try:
        sets = CardService.fetch_all_sets()
        return jsonify(sets)
    except Exception as e:
        logger.error(f"Error fetching sets: {str(e)}")
        return jsonify({"error": "Failed to fetch sets"}), 500


@card_routes.route("/save_set_selection", methods=["POST"])
def save_set_selection():
    """Save the selected set for a card"""
    try:
        data = request.json
        set_code = data.get("set_code")
        if not set_code:
            return jsonify({"error": "Set code is required"}), 400

        # Store the selected set (you might want to save this to your database)
        # For now, just return success
        return jsonify({"message": f"Set {set_code} selected successfully"}), 200
    except Exception as e:
        logger.error(f"Error saving set selection: {str(e)}")
        return jsonify({"error": "Failed to save set selection"}), 500


############################################################################################################
# Scan Operations
############################################################################################################
@card_routes.route("/scans/<int:scan_id>", methods=["GET"])
def get_scan_results(scan_id):
    try:
        scan = ScanService.get_scan_results(scan_id)
        if not scan:
            return jsonify({"error": "Scan not found"}), 404

        return jsonify(scan.to_dict())
    except Exception as e:
        logger.error(f"Error fetching scan results: {str(e)}")
        return jsonify({"error": "Failed to fetch scan results"}), 500


@card_routes.route("/scans", methods=["GET"])
def get_all_scans():
    try:
        scans = ScanService.get_all_scan_results()
        return jsonify(
            [
                {
                    "id": scan.id,
                    "created_at": scan.created_at.isoformat(),
                    "cards_scraped": len(scan.scan_results) if scan.scan_results else 0,
                    "sites_scraped": len(set(r.site_id for r in scan.scan_results)) if scan.scan_results else 0,
                }
                for scan in scans
            ]
        )
    except Exception as e:
        logger.error(f"Error fetching scans: {str(e)}")
        return jsonify({"error": "Failed to fetch scans"}), 500


@card_routes.route("/scans/", methods=["GET"])
def get_scan_history():
    """Get scan history without optimization results"""
    scans = ScanService.get_all_scan_results()
    return jsonify(
        [
            {
                "id": scan.id,
                "created_at": scan.created_at.isoformat(),
                "cards_scraped": len(scan.scan_results),
                "sites_scraped": len(set(r.site_id for r in scan.scan_results)),
                "scan_results": [r.to_dict() for r in scan.scan_results],
            }
            for scan in scans
        ]
    )


@card_routes.route("/scans/<int:scan_id>", methods=["DELETE"])
def delete_scan(scan_id):
    """Delete a scan by its ID."""
    try:
        result = ScanService.delete_scan(scan_id)
        if result:
            return jsonify({"message": "Scan deleted successfully"}), 200
        else:
            return jsonify({"error": "Scan not found"}), 404
    except Exception as e:
        logger.error(f"Error deleting scan: {str(e)}")
        return jsonify({"error": "Failed to delete scan"}), 500


############################################################################################################
# Site Operations
############################################################################################################
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
        logger.error(f"Error adding site: {str(e)}")
        return jsonify({"error": "Failed to add site"}), 500


@card_routes.route("/sites/<int:site_id>", methods=["PUT"])
def update_site(site_id):
    try:
        data = request.json
        if not data:
            return jsonify({"status": "warning", "message": "No data provided for update"}), 400

        updated_site = SiteService.update_site(site_id, data)
        if not updated_site:
            return (
                jsonify({"status": "info", "message": "No changes were needed - site data is already up to date"}),
                200,
            )

        return (
            jsonify(
                {
                    "status": "success",
                    "message": "Site updated successfully",
                    "site": updated_site.to_dict(),
                }
            ),
            200,
        )

    except ValueError as ve:
        return jsonify({"status": "warning", "message": str(ve)}), 400
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({"status": "error", "message": "An unexpected error occurred while updating the site"}), 500


@card_routes.route("/sites/<int:site_id>", methods=["DELETE"])
def delete_site(site_id):
    try:
        deleted = SiteService.delete_site(site_id)
        if deleted:
            return jsonify({"status": "success", "message": "Site deleted successfully"}), 200
        else:
            return jsonify({"status": "error", "message": "Site not found"}), 404
    except Exception as e:
        logger.error(f"Error deleting site: {str(e)}")
        return jsonify({"status": "error", "message": "Failed to delete site"}), 500


############################################################################################################
# Results Operations
############################################################################################################
@card_routes.route("/results", methods=["GET"])
def get_optimization_results():
    """Get recent optimization results"""
    results = OptimizationService.get_optimization_results()
    logger.info(f"Found {len(results)} optimization results")
    response = []
    for opt_result, scan, buylist in results:
        response.append(
            {
                "id": opt_result.scan_id,
                "created_at": opt_result.created_at.isoformat(),
                "solutions": opt_result.solutions,
                "status": opt_result.status,
                "message": opt_result.message,
                "sites_scraped": opt_result.sites_scraped,
                "cards_scraped": opt_result.cards_scraped,
                "errors": opt_result.errors,
                "buylist_name": buylist.name if buylist else None,
            }
        )

    # logger.info(f"Optimization results: {response}")
    return jsonify(response)


@card_routes.route("/results/<int:scan_id>", methods=["GET"])
def get_scan_optimization_result(scan_id):
    """Get optimization results for a specific scan"""
    opt_results = OptimizationService.get_optimization_results_by_scan(scan_id)
    if not opt_results or len(opt_results) == 0:
        return jsonify({"error": "No optimization results found"}), 404

    opt_result = opt_results[0]  # Get the first/latest result

    response = {
        "id": scan_id,
        "created_at": opt_result.created_at.isoformat(),
        "solutions": opt_result.solutions,
        "status": opt_result.status,
        "message": opt_result.message,
        "sites_scraped": opt_result.sites_scraped,
        "cards_scraped": opt_result.cards_scraped,
        "errors": opt_result.errors,
    }

    return jsonify(response)


@card_routes.route("/results/latest", methods=["GET"])
def get_latest_optimization_results():

    opt_result = OptimizationService.get_latest_optimization()
    if not opt_result:
        return jsonify({"error": "No optimization results found"}), 404

    response = {
        "id": opt_result.scan_id,
        "created_at": opt_result.created_at.isoformat(),
        "optimization": opt_result.to_dict(),
    }

    return jsonify(response)
