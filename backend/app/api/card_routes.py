import logging
import time
import aiohttp
from quart import Blueprint, request, jsonify

from app.services.card_service import CardService
from app.services.user_buylist_service import BuylistService
from app.services.user_buylist_card_service import UserBuylistCardService


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
        user_id = get_jwt_identity()
        if not user_id:
            return jsonify({"error": "User ID is required"}), 400

        # Call the service to delete the buylist
        async with flask_session_scope() as session:
            deleted = await BuylistService.delete_buylist(session, buylistId, user_id)
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
            return jsonify(updated_buylist), 201

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


@card_routes.route("/buylist/cards/delete-many", methods=["DELETE"])
@jwt_required
async def delete_multiple_buylist_cards():
    user_id = get_jwt_identity()
    data = await request.get_json()
    buylist_id = data.get("buylistId")
    cards = data.get("cards", [])

    async with flask_session_scope() as session:
        count = await UserBuylistCardService.delete_cards_from_buylist(session, buylist_id, user_id, cards)
        await session.commit()

    return jsonify({"deleted_count": count}), 200


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
        buylistId = data.get("buylistId")  # Ensure buylist id is provided

        if not user_id or not buylistId:
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


@card_routes.route("/card/fetch", methods=["GET"])
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


@card_routes.route("/card/suggestions", methods=["GET"])
@jwt_required
async def get_card_suggestions():
    query = request.args.get("query", "")
    suggestions = await CardService.get_card_suggestions(query)
    return jsonify(suggestions)


@card_routes.route("/card/<string:card_id>", methods=["GET"])
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


@card_routes.route("/card/<card_name>/sets", methods=["GET"])
@jwt_required
async def get_card_sets(card_name):
    """Get available sets for a specific card from Scryfall data"""
    try:
        async with flask_session_scope() as session:
            # Use your existing CardService to get Scryfall data
            card_data = await CardService.fetch_scryfall_card_data(
                session, card_name, set_code=None, language="en", version=None
            )

            if not card_data or "scryfall" not in card_data:
                logger.warning(f"No Scryfall data found for card: {card_name}")
                return jsonify([])

            # Extract sets from all_printings
            all_printings = card_data["scryfall"].get("all_printings", [])

            if not all_printings:
                logger.warning(f"No printings found for card: {card_name}")
                return jsonify([])

            # Create set options from the printings
            sets_seen = set()
            set_options = []

            for printing in all_printings:
                set_code = printing.get("set_code")
                set_name = printing.get("set_name")

                if set_code and set_name and set_code not in sets_seen:
                    sets_seen.add(set_code)
                    set_options.append({"value": set_code, "label": f"{set_code.upper()} - {set_name}"})

            # Sort by set code for consistency
            set_options.sort(key=lambda x: x["value"])

            logger.info(f"Found {len(set_options)} sets for card: {card_name}")
            return jsonify(set_options)

    except Exception as e:
        logger.error(f"Error getting sets for card {card_name}: {str(e)}")
        return jsonify([])
