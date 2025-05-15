import logging
import aiohttp
from quart import Blueprint, request, jsonify

from app.services.card_service import CardService
from app.services.scan_service import ScanService
from app.services.site_service import SiteService
from app.services.user_buylist_service import BuylistService
from app.services.optimization_service import OptimizationService
from app.services.user_buylist_card_service import UserBuylistCardService

from app.tasks.optimization_tasks import celery_app, start_scraping_task
from celery.result import AsyncResult
from app.utils.async_context_manager import flask_session_scope
from quart_jwt_extended import jwt_required, get_jwt_identity

logger = logging.getLogger(__name__)

# Defining Blueprint for Card Routes
card_routes = Blueprint("card_routes", __name__)


############################################################################################################
# Buylist Operations
############################################################################################################
@card_routes.route("/buylists", methods=["GET"])
@jwt_required
async def get_buylists():

    user_id = get_jwt_identity()
    logger.info(f"Got user: {user_id}")
    async with flask_session_scope() as session:
        try:
            buylists = await BuylistService.get_all_buylists(session=session, user_id=user_id)
            return jsonify(buylists), 200

        except Exception as e:
            logger.exception(f"Error fetching buylists: {e}")
            return jsonify({"error": str(e)}), 500


@card_routes.route("/buylists", methods=["POST"])
@jwt_required
async def create_buylist():
    try:
        data = await request.get_json()
        name = data.get("name", "Untitled Buylist")
        user_id = get_jwt_identity()
        logger.info(f"got user {user_id}")

        if not user_id:
            return jsonify({"error": "User ID is required"}), 400

        logger.info(f"Creating new buylist '{name}' for user {user_id}")
        async with flask_session_scope() as session:
            new_buylist = await BuylistService.create_buylist(session, name=name, user_id=user_id)
            await session.commit()
            return jsonify(new_buylist), 201  # ✅ Already a dict

    except Exception as e:
        logger.error(f"Error creating buylist: {str(e)}")
        return jsonify({"error": "Failed to create buylist"}), 500


@card_routes.route("/buylists/<int:buylistId>", methods=["GET"])
@jwt_required
async def load_buylist(buylistId=None):
    """Load a saved buylist by ID or all buylists' cards if ID is None."""
    try:
        user_id = get_jwt_identity()
        logger.info(f"got user {user_id}")
        if not user_id:
            return jsonify({"error": "User ID is required"}), 400

        async with flask_session_scope() as session:
            if buylistId:
                logger.info(f"Loading buylist {buylistId} for user {user_id}")
                buylist_cards = await UserBuylistCardService.get_buylist_cards_by_id(session, buylistId)
                logger.info(f"Loaded {len(buylist_cards)} cards for buylist {buylistId}")
            else:
                logger.info(f"Loading all buylist cards for user {user_id}")
                buylist_cards = await UserBuylistCardService.get_all_user_buylist_cards(session, user_id)
                logger.info(f"Loaded all {len(buylist_cards)} cards for user {user_id}")

            return jsonify(buylist_cards), 200

    except Exception as e:
        logger.error(f"Error loading buylist: {str(e)}")
        return jsonify({"error": "Failed to load buylist"}), 500


@card_routes.route("/buylists/<int:buylistId>", methods=["DELETE"])
@jwt_required
async def delete_buylist(buylistId):
    """
    Delete a buylist by its ID.
    """
    try:
        logger.info("Trying to delete")
        user_id = get_jwt_identity()
        if not user_id:
            return jsonify({"error": "User ID is required"}), 400

        # Call the service to delete the buylist
        async with flask_session_scope() as session:
            deleted = await UserBuylistCardService.delete_buylist(session, buylistId, user_id)
            await session.commit()
            if deleted:

                return jsonify({"message": "Buylist deleted successfully"}), 200
            else:
                return jsonify({"error": "Buylist not found or could not be deleted"}), 404
    except Exception as e:
        logger.error(f"Error deleting buylist {buylistId}: {str(e)}")
        return jsonify({"error": "Failed to delete buylist"}), 500


@card_routes.route("/buylists/<int:buylistId>/cards", methods=["POST"])
@jwt_required
async def add_cards_to_buylist(buylistId):
    """
    Add cards to an existing buylist.
    """
    try:
        data = await request.get_json()
        user_id = get_jwt_identity()
        cards = data.get("cards", [])

        if not user_id:
            return jsonify({"error": "User ID is required"}), 400

        if not cards:
            return jsonify({"error": "No cards provided"}), 400

        logger.info(f"Adding cards to buylist {buylistId} for user {user_id}")
        async with flask_session_scope() as session:
            updated_buylist = await UserBuylistCardService.add_cards_to_buylist(session, buylistId, user_id, cards)
            await session.commit()
            return jsonify(updated_buylist.to_dict()), 201

    except Exception as e:
        logger.error(f"Error adding cards to buylist {buylistId}: {str(e)}")
        return jsonify({"error": "Failed to add cards to buylist"}), 500


@card_routes.route("/buylists/<int:buylistId>/rename", methods=["PUT"])
@jwt_required
async def rename_buylist(buylistId):
    """
    Rename an existing buylist without affecting its cards.
    """
    try:
        data = await request.get_json()
        new_name = data.get("name")
        user_id = get_jwt_identity()

        if not user_id or not new_name:
            return jsonify({"error": "User ID and new buylist name are required"}), 400

        async with flask_session_scope() as session:
            updated_buylist = await BuylistService.update_user_buylist_name(session, buylistId, user_id, new_name)
            await session.commit()
            return jsonify(updated_buylist), 200

    except Exception as e:
        logger.error(f"Error renaming buylist {buylistId}: {str(e)}")
        return jsonify({"error": "Failed to rename buylist"}), 500


@card_routes.route("/buylists/top", methods=["GET"])
@jwt_required
async def get_top_buylists():
    user_id = get_jwt_identity()
    logger.info(f"got user {user_id}")
    async with flask_session_scope() as session:
        try:
            top_buylists = await BuylistService.get_top_buylists(session=session, user_id=user_id)
            return jsonify(top_buylists)
        except Exception as e:
            logger.exception(f"Error fetching top buylists: {e}")
            return jsonify({"error": str(e)}), 500


############################################################################################################
# Buylist Card Operations
############################################################################################################


@card_routes.route("/buylist/cards", methods=["DELETE"])
@jwt_required
async def delete_cards():
    """
    Delete specific cards from a buylist.

    Expects a JSON payload with:
    - buylistId: The ID of the buylist
    - user_id: The ID of the user
    - cards: A list of cards to delete
    """
    data = await request.get_json()
    buylistId = data.get("buylistId")
    user_id = get_jwt_identity()
    cards = data.get("cards")

    if not buylistId or not user_id or not cards:
        return jsonify({"error": "Buylist ID, user ID, and cards are required"}), 400

    deleted_cards = []
    async with flask_session_scope() as session:
        for card in cards:
            card_name = card.get("name")
            quantity = card.get("quantity", 1)

            try:
                # Delete the card
                deleted = await UserBuylistCardService.delete_card_from_buylist(
                    session, buylist_id=buylistId, card_name=card_name, quantity=quantity, user_id=user_id
                )
                if deleted:
                    deleted_cards.append({"name": card_name, "quantity": quantity})
                else:
                    logger.warning(f"Card not found or could not be deleted: {card_name}")

            except Exception as e:
                logger.error(f"Error deleting cards: {str(e)}")
                return jsonify({"error": "Failed to delete cards"}), 500
        await session.commit()
    return jsonify({"deletedCards": deleted_cards}), 200


@card_routes.route("/buylist/cards/import", methods=["POST"])
@jwt_required
async def import_cards_to_buylist():
    """Import cards into a buylist from a text input."""
    try:
        data = await request.get_json()
        buylistId = data.get("buylistId")
        cards = data.get("cards", [])
        user_id = get_jwt_identity()

        if not user_id:
            logger.error("User ID is missing in the request")
            return jsonify({"error": "User ID is required"}), 400

        if not buylistId or not cards:
            return jsonify({"error": "Buylist ID and cards are required"}), 400

        added_cards = []
        not_found_cards = []

        async with flask_session_scope() as session:
            for card in cards:
                card_name = card.get("name")
                quantity = card.get("quantity", 1)
                set_name = card.get("set_name", None)
                language = card.get("language", "English")
                quality = card.get("quality", "NM")
                version = card.get("version", "Standard")
                foil = card.get("foil", False)

                # Validate card existence (e.g., via Scryfall API)
                if await CardService.is_valid_card_name(card_name):
                    await UserBuylistCardService.add_user_buylist_card(
                        session,
                        name=card_name,
                        quantity=quantity,
                        buylist_id=buylistId,
                        user_id=user_id,
                        set_name=set_name,
                        language=language,
                        quality=quality,
                        version=version,
                        foil=foil,
                    )
                    logger.info(f"card {card_name} found")
                    added_cards.append({"name": card_name, "quantity": quantity})
                else:
                    logger.info(f"card {card_name} not found")
                    not_found_cards.append({"name": card_name})
            await session.commit()
            return jsonify({"addedCards": added_cards, "notFoundCards": not_found_cards}), 200

    except Exception as e:
        logger.error(f"Error importing cards: {str(e)}")
        return jsonify({"error": "Failed to import cards"}), 500


@card_routes.route("/buylist/cards/<int:card_id>", methods=["PUT"])
@jwt_required
async def update_user_buylist_card(card_id):
    """Update a specific card in the user's buylist."""
    try:
        data = await request.get_json()
        user_id = get_jwt_identity()
        buylistid = data.get("buylistId")  # Ensure buylist id is provided

        if not user_id or not buylistid:
            return jsonify({"error": "User ID and Buylist ID are required"}), 400

        logger.info(f"Received update request for card {card_id}: {data}")

        async with flask_session_scope() as session:
            updated_card = await UserBuylistCardService.update_user_buylist_card(session, card_id, user_id, data)
            await session.commit()
            if not updated_card:
                return jsonify({"error": "Card not found in user's buylist"}), 404

            result = updated_card
            logger.info(f"Successfully updated card: {result}")
            return jsonify(result), 200

    except Exception as e:
        logger.error(f"Error updating card: {str(e)}")
        return jsonify({"error": f"Failed to update card: {str(e)}"}), 500


############################################################################################################
# Card Operations
############################################################################################################


@card_routes.route("/fetch_card", methods=["GET"])
@jwt_required
async def fetch_scryfall_card():

    card_name = request.args.get("name")
    set_code = request.args.get("set_code")
    language = request.args.get("language")
    version = request.args.get("version")

    logger.info(f"Fetching card with params: name={card_name}, set_code={set_code}, lang={language}, ver={version}")

    if not card_name:
        return jsonify({"error": "Missing parameter", "details": "Card name is required"}), 400

    try:
        async with flask_session_scope() as session:
            card_data = await CardService.fetch_scryfall_card_data(session, card_name, set_code, language, version)
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
                            "params": {
                                "name": card_name,
                                "set_code": set_code,
                                "language": language,
                                "version": version,
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
                                "loyalty": None,
                            },
                            "available_languages": [],
                            "available_versions": {},
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
@jwt_required
async def get_card_suggestions():
    query = request.args.get("query", "")
    suggestions = await CardService.get_card_suggestions(query)
    return jsonify(suggestions)


@card_routes.route("/scryfall/card/<string:card_id>", methods=["GET"])
@jwt_required
async def get_card_by_scryfall_id(card_id):
    """
    Fetch a card from Scryfall using its unique ID (UUID).
    """
    logger.info(f"Fetching Scryfall card by ID: {card_id}")
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://api.scryfall.com/cards/{card_id}"
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return jsonify(data)
                else:
                    logger.warning(f"Scryfall returned {response.status} for card ID: {card_id}")
                    return jsonify({"error": "Card not found", "id": card_id}), 404
    except Exception as e:
        logger.error(f"Error fetching card by Scryfall ID: {str(e)}", exc_info=True)
        return jsonify({"error": "Internal Server Error", "details": str(e)}), 500


############################################################################################################
# Task Operations
############################################################################################################


@card_routes.route("/task_status/<task_id>", methods=["GET"])
@jwt_required
async def task_status(task_id):
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

        # logger.info(
        #     f"Task {task_id} state: {task.state}, status: {task.info.get('status', '')}, progress: {task.info.get('progress', 0)}"
        # )
        return jsonify(response), 200

    except Exception as e:
        logger.exception(f"Error checking task status: {str(e)}")
        return jsonify({"state": "ERROR", "status": "Error checking task status", "error": str(e)}), 500


############################################################################################################
# Optimization Operations
############################################################################################################


@card_routes.route("/start_scraping", methods=["POST"])
@jwt_required
async def start_scraping():
    """Starts the scraping task."""
    data = await request.get_json()
    # logger.info("Received data: %s", data)

    user_id = get_jwt_identity()
    logger.info(f"got user {user_id}")

    buylist_id = int(data.get("buylist_id", None))
    site_ids = data.get("sites", [])
    card_list_from_frontend = data.get("card_list", [])
    strategy = data.get("strategy", "milp")
    min_store = data.get("min_store", 1)
    find_min_store = data.get("find_min_store", False)
    min_age_seconds = data.get("min_age_seconds", 1800)
    strict_preferences = data.get("strict_preferences", False)
    user_preferences = data.get("user_preferences", {})
    weights = data.get("weights", {})

    if not site_ids or not card_list_from_frontend:
        return jsonify({"error": "Missing site_ids or card_list"}), 400
    logger.info(f"Task start_scraping about to start")
    task = start_scraping_task.apply_async(
        args=[
            site_ids,
            card_list_from_frontend,
            strategy,
            min_store,
            find_min_store,
            min_age_seconds,
            buylist_id,
            user_id,
            strict_preferences,
            user_preferences,
            weights,
        ]
    )
    return jsonify({"task_id": task.id}), 202


@card_routes.route("/purchase_order", methods=["POST"])
@jwt_required
async def generate_purchase_links():
    try:
        data = await request.get_json()
        purchase_data = data.get("purchase_data", [])

        async with flask_session_scope() as session:
            active_sites = {site.id: site for site in await SiteService.get_all_sites(session)}
            results = await CardService.generate_purchase_links(purchase_data, active_sites)
            # logger.info(f"return data: {results}")
            return jsonify(results), 200

    except Exception as e:
        logger.error(f"Error generating purchase links: {str(e)}")
        return jsonify({"error": "Failed to generate purchase links"}), 500


############################################################################################################
# Set Operations
############################################################################################################


@card_routes.route("/sets", methods=["GET"])
@jwt_required
async def get_sets():
    try:
        sets = await CardService.fetch_all_sets()
        return jsonify(sets)
    except Exception as e:
        logger.error(f"Error fetching sets: {str(e)}")
        return jsonify({"error": "Failed to fetch sets"}), 500


############################################################################################################
# Scan Operations
############################################################################################################


@card_routes.route("/scans/<int:scan_id>", methods=["GET"])
@jwt_required
async def get_scan_by_id(scan_id):
    async with flask_session_scope() as session:
        try:
            scan = await ScanService.get_scan_results_by_scan_id(session, scan_id)
            if not scan:
                return jsonify({"error": "Scan not found"}), 404
            return jsonify(scan.to_dict())
        except Exception as e:
            logger.error(f"Error fetching scan results: {str(e)}")
            return jsonify({"error": "Failed to fetch scan results"}), 500


@card_routes.route("/scans", methods=["GET"])
@jwt_required
async def get_all_scans():
    async with flask_session_scope() as session:
        try:
            scans = await ScanService.get_all_scans(session)
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
@jwt_required
async def get_scan_history():
    """Get scan history without optimization results"""
    async with flask_session_scope() as session:
        scans = await ScanService.get_all_scans(session)
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


@card_routes.route("/scans", methods=["DELETE"])
@jwt_required
async def delete_scans():
    """
    Delete one or more scans.

    Expects a JSON payload with:
    - user_id: The ID of the user
    - scan_ids: A list of scan IDs to delete
    """
    try:
        data = await request.get_json()
        user_id = get_jwt_identity()
        scan_ids = data.get("scan_ids")

        if not user_id or not scan_ids:
            return jsonify({"error": "user_id and scan_ids are required"}), 400

        async with flask_session_scope() as session:
            deleted, errors = await ScanService.delete_scans(session, scan_ids)

        return jsonify({"deleted": deleted, "errors": errors}), 200 if deleted else 400

    except Exception as e:
        logger.error(f"Error during bulk scan deletion: {e}", exc_info=True)
        return jsonify({"error": "Bulk deletion failed"}), 500


############################################################################################################
# Site Operations
############################################################################################################


@card_routes.route("/sites", methods=["GET"])
@jwt_required
async def get_sites():
    async with flask_session_scope() as session:
        try:
            sites = await SiteService.get_all_sites(session=session)
            return jsonify([site.to_dict() for site in sites])

        except Exception as e:
            logger.exception(f"Error fetching sites: {e}")
            return jsonify({"error": str(e)}), 500


@card_routes.route("/sites", methods=["POST"])
@jwt_required
async def add_site():
    try:
        data = await request.get_json()
        async with flask_session_scope() as session:
            new_site = await SiteService.add_site(session, data)
            await session.commit()
            return jsonify(new_site.to_dict()), 201
    except Exception as e:
        logger.error(f"Error adding site: {str(e)}")
        return jsonify({"error": "Failed to add site"}), 500


@card_routes.route("/sites/<int:site_id>", methods=["PUT"])
@jwt_required
async def update_site(site_id):
    try:
        data = await request.get_json()
        if not data:
            return jsonify({"status": "warning", "message": "No data provided for update"}), 400

        async with flask_session_scope() as session:
            updated_site = await SiteService.update_site(session, site_id, data)
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
@jwt_required
async def delete_site(site_id):
    try:
        async with flask_session_scope() as session:
            deleted = await SiteService.delete_site(session, site_id)
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
@jwt_required
async def get_optimization_results():
    """Get recent optimization results"""
    async with flask_session_scope() as session:
        results = await OptimizationService.get_optimization_results(session)
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
@jwt_required
async def get_scan_optimization_result(scan_id):
    """Get optimization results for a specific scan"""
    async with flask_session_scope() as session:
        opt_results = await OptimizationService.get_optimization_results_by_scan(session, scan_id)
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
@jwt_required
async def get_latest_optimization_results():
    async with flask_session_scope() as session:
        opt_result = await OptimizationService.get_latest_optimization(session)
        if not opt_result:
            return jsonify({"error": "No optimization results found"}), 404

        response = {
            "id": opt_result.scan_id,
            "created_at": opt_result.created_at.isoformat(),
            "optimization": opt_result.to_dict(),
        }

        return jsonify(response)
