import logging
from decimal import Decimal, InvalidOperation
from quart import Blueprint, request, jsonify

from app.services.watchlist_service import WatchlistService
from app.services.mtgstocks_service import MTGStocksService
from app.utils.async_context_manager import flask_session_scope
from quart_jwt_extended import jwt_required, get_jwt_identity

logger = logging.getLogger(__name__)

# Defining Blueprint for Watchlist Routes
watchlist_routes = Blueprint("watchlist_routes", __name__)


############################################################################################################
# Watchlist Operations
############################################################################################################


@watchlist_routes.route("/watchlist", methods=["GET"])
@jwt_required
async def get_user_watchlist():
    """Get all watchlist items for the authenticated user"""
    try:
        user_id = get_jwt_identity()

        async with flask_session_scope() as session:
            watchlist_items = await WatchlistService.get_user_watchlist(session, user_id)
            return jsonify([item.to_dict(include_latest_alert=True) for item in watchlist_items])
    except Exception as e:
        logger.error(f"Error fetching user watchlist: {str(e)}")
        return jsonify({"error": "Failed to fetch watchlist"}), 500


@watchlist_routes.route("/watchlist", methods=["POST"])
@jwt_required
async def add_to_watchlist():
    """Add a new item to the user's watchlist"""
    try:
        user_id = get_jwt_identity()
        data = await request.get_json()

        # Validate required fields
        card_name = data.get("card_name")
        if not card_name:
            return jsonify({"error": "card_name is required"}), 400

        # Optional fields
        set_code = data.get("set_code")
        mtgstocks_id = data.get("mtgstocks_id")
        mtgstocks_url = data.get("mtgstocks_url")

        # Handle target_price
        target_price = None
        if data.get("target_price") is not None:
            try:
                target_price = Decimal(str(data.get("target_price")))
            except (InvalidOperation, TypeError):
                return jsonify({"error": "Invalid target_price format"}), 400

        # If MTGStocks data not provided, try to find it automatically
        if not mtgstocks_id:
            try:
                async with MTGStocksService() as mtg_service:
                    card_data = await mtg_service.search_and_get_best_match(card_name, set_code)
                    if card_data:
                        mtgstocks_id = card_data.get("id")
                        mtgstocks_url = card_data.get("url")
                        if not set_code and card_data.get("set_code"):
                            set_code = card_data.get("set_code")

                        logger.info(f"Auto-found MTGStocks data for {card_name}: ID {mtgstocks_id}")
            except Exception as e:
                logger.warning(f"Could not auto-find MTGStocks data for {card_name}: {str(e)}")

        # Create the watchlist item within a single transaction
        async with flask_session_scope() as session:
            try:
                watchlist_item = await WatchlistService.create_watchlist_item(
                    session=session,
                    user_id=user_id,
                    card_name=card_name,
                    set_code=set_code,
                    target_price=target_price,
                    mtgstocks_id=mtgstocks_id,
                    mtgstocks_url=mtgstocks_url,
                )
                # Commit within the same transaction
                await session.commit()

                # Return the created item without trying to access relationships
                response_data = watchlist_item.to_dict(include_latest_alert=False)

                # Add a flag if MTGStocks data was auto-found
                if mtgstocks_id and not data.get("mtgstocks_id"):
                    response_data["auto_found_mtgstocks"] = True

                return jsonify(response_data), 201

            except ValueError as ve:
                # Session will auto-rollback on error due to context manager
                return jsonify({"error": str(ve)}), 400
            except Exception as e:
                # Session will auto-rollback on error
                logger.error(f"Database error creating watchlist item: {str(e)}")
                return jsonify({"error": "Failed to create watchlist item"}), 500

    except Exception as e:
        logger.error(f"Error adding to watchlist: {str(e)}")
        return jsonify({"error": "Failed to add item to watchlist"}), 500


@watchlist_routes.route("/watchlist/<int:watchlist_id>", methods=["PUT"])
@jwt_required
async def update_watchlist_item(watchlist_id):
    """Update a watchlist item"""
    try:
        user_id = get_jwt_identity()
        data = await request.get_json()

        # Handle target_price if provided
        updates = {}
        if "target_price" in data:
            if data["target_price"] is not None:
                try:
                    updates["target_price"] = Decimal(str(data["target_price"]))
                except (InvalidOperation, TypeError):
                    return jsonify({"error": "Invalid target_price format"}), 400
            else:
                updates["target_price"] = None

        # Other allowed updates
        for field in ["set_code", "mtgstocks_id", "mtgstocks_url"]:
            if field in data:
                updates[field] = data[field]

        async with flask_session_scope() as session:
            try:
                watchlist_item = await WatchlistService.update_watchlist_item(session, watchlist_id, user_id, **updates)
                if not watchlist_item:
                    return jsonify({"error": "Watchlist item not found"}), 404

                await session.commit()
                await session.refresh(watchlist_item)

                # Convert to dict without trying to access relationships
                result_dict = watchlist_item.to_dict(include_latest_alert=False)
                return jsonify(result_dict)

            except Exception as e:
                error_msg = str(e)
                logger.error(f"Error updating watchlist item: {error_msg}")
                return jsonify({"error": "Failed to update watchlist item"}), 500

    except Exception as e:
        logger.error(f"Error updating watchlist item: {str(e)}")
        return jsonify({"error": "Failed to update watchlist item"}), 500


@watchlist_routes.route("/watchlist/<int:watchlist_id>", methods=["DELETE"])
@jwt_required
async def remove_from_watchlist(watchlist_id):
    """Remove an item from the user's watchlist"""
    try:
        user_id = get_jwt_identity()

        async with flask_session_scope() as session:
            success = await WatchlistService.remove_from_watchlist(session, watchlist_id, user_id)
            if not success:
                return jsonify({"error": "Watchlist item not found"}), 404

            await session.commit()
            return jsonify({"message": "Item removed from watchlist"}), 200
    except Exception as e:
        logger.error(f"Error removing from watchlist: {str(e)}")
        return jsonify({"error": "Failed to remove item from watchlist"}), 500


@watchlist_routes.route("/watchlist/delete-many", methods=["DELETE"])
@jwt_required
async def delete_multiple_watchlist_items():
    """Delete multiple watchlist items"""
    try:
        user_id = get_jwt_identity()
        data = await request.get_json()
        watchlist_ids = data.get("ids", [])

        if not watchlist_ids:
            return jsonify({"error": "No watchlist item IDs provided"}), 400

        async with flask_session_scope() as session:
            deleted, errors = await WatchlistService.delete_watchlist_items(session, watchlist_ids, user_id)
            await session.commit()

            if errors:
                logger.warning(f"Errors during bulk watchlist deletion: {errors}")

            return jsonify(
                {"deleted": deleted, "errors": errors, "message": f"Successfully deleted {len(deleted)} item(s)"}
            ), (200 if deleted else 400)
    except Exception as e:
        logger.error(f"Error during bulk watchlist deletion: {str(e)}")
        return jsonify({"error": "Bulk deletion failed"}), 500


############################################################################################################
# Price Alert Operations
############################################################################################################


@watchlist_routes.route("/watchlist/alerts", methods=["GET"])
@jwt_required
async def get_price_alerts():
    """Get recent price alerts for the user"""
    try:
        user_id = get_jwt_identity()
        hours = int(request.args.get("hours", 24))  # Default to last 24 hours

        async with flask_session_scope() as session:
            alerts = await WatchlistService.get_recent_alerts(session, user_id, hours)
            # Use the standard to_dict method for alerts
            return jsonify([alert.to_dict() for alert in alerts])
    except Exception as e:
        logger.error(f"Error fetching price alerts: {str(e)}")
        return jsonify({"error": "Failed to fetch price alerts"}), 500


@watchlist_routes.route("/watchlist/alerts/mark-viewed", methods=["POST"])
@jwt_required
async def mark_alerts_viewed():
    """Mark price alerts as viewed"""
    try:
        user_id = get_jwt_identity()
        data = await request.get_json()
        alert_ids = data.get("alert_ids", [])

        if not alert_ids:
            return jsonify({"error": "No alert IDs provided"}), 400

        async with flask_session_scope() as session:
            updated_count = await WatchlistService.mark_alerts_as_viewed(session, alert_ids, user_id)
            await session.commit()

            return jsonify({"message": f"Marked {updated_count} alert(s) as viewed", "updated_count": updated_count})
    except Exception as e:
        logger.error(f"Error marking alerts as viewed: {str(e)}")
        return jsonify({"error": "Failed to mark alerts as viewed"}), 500


############################################################################################################
# Price Checking Operations
############################################################################################################


@watchlist_routes.route("/watchlist/<int:watchlist_id>/check-prices", methods=["POST"])
@jwt_required
async def check_prices_for_item(watchlist_id):
    """Manually trigger price checking for a specific watchlist item"""
    try:
        user_id = get_jwt_identity()
        data = await request.get_json()
        market_price = None

        if data and data.get("market_price"):
            try:
                market_price = Decimal(str(data.get("market_price")))
            except (InvalidOperation, TypeError):
                return jsonify({"error": "Invalid market_price format"}), 400

        async with flask_session_scope() as session:
            # First verify the watchlist item belongs to the user
            watchlist_items = await WatchlistService.get_user_watchlist(session, user_id)
            watchlist_item = next((item for item in watchlist_items if item.id == watchlist_id), None)

            if not watchlist_item:
                return jsonify({"error": "Watchlist item not found"}), 404

            # Get fresh market price if not provided and MTGStocks ID available
            if not market_price and watchlist_item.mtgstocks_id:
                try:
                    async with MTGStocksService() as mtg_service:
                        market_price = await mtg_service.get_market_price(watchlist_item.mtgstocks_id)
                except Exception as e:
                    logger.warning(f"Could not fetch market price: {str(e)}")

            # Check prices and create alerts
            alerts = await WatchlistService.check_prices_for_watchlist_item(session, watchlist_item, market_price)
            await session.commit()

            return jsonify(
                {
                    "message": f"Price check completed for {watchlist_item.card_name}",
                    "alerts_created": len(alerts),
                    "market_price": float(market_price) if market_price else None,
                    "alerts": [alert.to_dict() for alert in alerts],
                }
            )
    except Exception as e:
        logger.error(f"Error checking prices for watchlist item: {str(e)}")
        return jsonify({"error": "Failed to check prices"}), 500


@watchlist_routes.route("/watchlist/check-all-prices", methods=["POST"])
@jwt_required
async def check_all_prices():
    """Manually trigger price checking for all user's watchlist items"""
    try:
        user_id = get_jwt_identity()

        async with flask_session_scope() as session:
            watchlist_items = await WatchlistService.get_user_watchlist(session, user_id)

            total_alerts = 0
            items_checked = 0

            async with MTGStocksService() as mtg_service:
                for item in watchlist_items:
                    try:
                        # Get market price if available
                        market_price = None
                        if item.mtgstocks_id:
                            try:
                                market_price = await mtg_service.get_market_price(item.mtgstocks_id)
                            except Exception as e:
                                logger.warning(f"Could not get market price for {item.card_name}: {str(e)}")

                        alerts = await WatchlistService.check_prices_for_watchlist_item(session, item, market_price)
                        total_alerts += len(alerts)
                        items_checked += 1

                        # Small delay between items to be respectful
                        if items_checked < len(watchlist_items):
                            import asyncio

                            await asyncio.sleep(1)

                    except Exception as e:
                        logger.error(f"Error checking prices for item {item.id}: {str(e)}")
                        continue

            await session.commit()

            return jsonify(
                {
                    "message": f"Price check completed for {items_checked} item(s)",
                    "items_checked": items_checked,
                    "total_alerts_created": total_alerts,
                }
            )
    except Exception as e:
        logger.error(f"Error checking all prices: {str(e)}")
        return jsonify({"error": "Failed to check prices for all items"}), 500


############################################################################################################
# MTGStocks Integration Endpoints
############################################################################################################


@watchlist_routes.route("/mtgstocks/search/<card_name>", methods=["GET"])
@jwt_required
async def search_mtgstocks(card_name):
    """Search for a card on MTGStocks"""
    try:
        set_code = request.args.get("set_code")
        limit = int(request.args.get("limit", 10))

        async with MTGStocksService() as mtg_service:
            # Get search results
            search_results = await mtg_service.search_cards(card_name, limit=limit)

            if not search_results:
                return jsonify({"message": "No cards found", "card_name": card_name, "results": []})

            # If set_code provided, try to find best match with pricing
            if set_code:
                best_match = await mtg_service.search_and_get_best_match(card_name, set_code)
                if best_match:
                    return jsonify(
                        {
                            "message": "Found card with pricing data",
                            "card_name": card_name,
                            "set_code": set_code,
                            "best_match": best_match,
                            "results": search_results,
                        }
                    )

            return jsonify(
                {"message": f"Found {len(search_results)} card(s)", "card_name": card_name, "results": search_results}
            )

    except Exception as e:
        logger.error(f"Error searching MTGStocks: {str(e)}")
        return jsonify({"error": "MTGStocks search failed"}), 500


@watchlist_routes.route("/mtgstocks/price/<int:mtgstocks_id>", methods=["GET"])
@jwt_required
async def get_mtgstocks_price_endpoint(mtgstocks_id):
    """Get current price and details from MTGStocks"""
    try:
        async with MTGStocksService() as mtg_service:
            card_details = await mtg_service.get_card_details(mtgstocks_id)

            if not card_details:
                return jsonify({"error": "Card not found or unable to fetch data", "mtgstocks_id": mtgstocks_id}), 404

            return jsonify(
                {
                    "message": "Successfully fetched card data",
                    "mtgstocks_id": mtgstocks_id,
                    "card_details": card_details,
                }
            )

    except Exception as e:
        logger.error(f"Error fetching MTGStocks price: {str(e)}")
        return jsonify({"error": "MTGStocks price fetch failed"}), 500


@watchlist_routes.route("/mtgstocks/auto-link", methods=["POST"])
@jwt_required
async def auto_link_mtgstocks():
    """Automatically find and link MTGStocks data for watchlist items missing it"""
    try:
        user_id = get_jwt_identity()
        data = await request.get_json()
        watchlist_ids = data.get("watchlist_ids", [])  # Specific items, or empty for all

        async with flask_session_scope() as session:
            # Get user's watchlist items
            all_items = await WatchlistService.get_user_watchlist(session, user_id)

            # Filter to items that need MTGStocks linking
            items_to_link = []
            if watchlist_ids:
                items_to_link = [item for item in all_items if item.id in watchlist_ids and not item.mtgstocks_id]
            else:
                items_to_link = [item for item in all_items if not item.mtgstocks_id]

            if not items_to_link:
                return jsonify(
                    {"message": "No items found that need MTGStocks linking", "items_processed": 0, "items_linked": 0}
                )

            linked_count = 0
            errors = []

            async with MTGStocksService() as mtg_service:
                for item in items_to_link:
                    try:
                        # Search for the card
                        card_data = await mtg_service.search_and_get_best_match(item.card_name, item.set_code)

                        if card_data and card_data.get("id"):
                            # Update the watchlist item
                            await WatchlistService.update_watchlist_item(
                                session,
                                item.id,
                                user_id,
                                mtgstocks_id=card_data["id"],
                                mtgstocks_url=card_data.get("url"),
                            )
                            linked_count += 1
                            logger.info(f"Linked {item.card_name} to MTGStocks ID {card_data['id']}")
                        else:
                            errors.append(
                                {
                                    "watchlist_id": item.id,
                                    "card_name": item.card_name,
                                    "error": "No MTGStocks match found",
                                }
                            )

                        # Small delay between requests
                        import asyncio

                        await asyncio.sleep(1)

                    except Exception as e:
                        error_msg = str(e)
                        errors.append({"watchlist_id": item.id, "card_name": item.card_name, "error": error_msg})
                        logger.error(f"Error auto-linking {item.card_name}: {error_msg}")

            await session.commit()

            return jsonify(
                {
                    "message": f"Auto-linking completed. Linked {linked_count} of {len(items_to_link)} items.",
                    "items_processed": len(items_to_link),
                    "items_linked": linked_count,
                    "errors": errors,
                }
            )

    except Exception as e:
        logger.error(f"Error in auto-link MTGStocks: {str(e)}")
        return jsonify({"error": "Auto-linking failed"}), 500


############################################################################################################
# Utility Routes
############################################################################################################


@watchlist_routes.route("/watchlist/stats", methods=["GET"])
@jwt_required
async def get_watchlist_stats():
    """Get statistics about the user's watchlist"""
    try:
        user_id = get_jwt_identity()

        async with flask_session_scope() as session:
            watchlist_items = await WatchlistService.get_user_watchlist(session, user_id)
            alerts = await WatchlistService.get_recent_alerts(session, user_id, 24)

            # Calculate stats
            total_items = len(watchlist_items)
            items_with_targets = len([item for item in watchlist_items if item.target_price])
            items_with_mtgstocks = len([item for item in watchlist_items if item.mtgstocks_id])
            unviewed_alerts = len([alert for alert in alerts if not alert.is_viewed])

            # Items needing price check
            items_needing_check = await WatchlistService.get_items_needing_price_check(session, 24)
            user_items_needing_check = [item for item in items_needing_check if item.user_id == user_id]

            return jsonify(
                {
                    "total_items": total_items,
                    "items_with_targets": items_with_targets,
                    "items_with_mtgstocks": items_with_mtgstocks,
                    "recent_alerts": len(alerts),
                    "unviewed_alerts": unviewed_alerts,
                    "items_needing_check": len(user_items_needing_check),
                }
            )
    except Exception as e:
        logger.error(f"Error getting watchlist stats: {str(e)}")
        return jsonify({"error": "Failed to get watchlist statistics"}), 500
