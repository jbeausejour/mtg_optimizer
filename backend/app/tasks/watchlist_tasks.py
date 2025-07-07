import asyncio
import logging
import aiohttp
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from decimal import Decimal

from sqlalchemy import select, delete, func, and_
from app import create_app

from celery import Task
from app.tasks.celery_instance import celery_app
from app.utils.async_context_manager import celery_session_scope
from app.services.watchlist_service import WatchlistService
from app.services.mtgstocks_service import get_mtgstocks_price, MTGStocksService
from app.models.watchlist import Watchlist, PriceAlert
import nest_asyncio

# Apply nest_asyncio at module level
nest_asyncio.apply()
logger = logging.getLogger(__name__)


class CallbackTask(Task):
    """Base task class with proper async session handling"""

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(f"Task {task_id} failed: {exc}")

    def on_success(self, retval, task_id, args, kwargs):
        logger.info(f"Task {task_id} completed successfully")


@celery_app.task(bind=True, base=CallbackTask, name="watchlist.check_all_prices")
def check_all_watchlist_prices(self, max_age_hours: int = 1, force_check: bool = False):
    """
    Periodic task to check prices for all watchlist items that need checking

    Args:
        max_age_hours: Only check items not checked in this many hours
        force_check: If True, check all items regardless of last check time
    """

    async def run():
        app = create_app()
        async with app.app_context():
            logger.info(f"🔍 Starting watchlist price check cycle (max_age: {max_age_hours}h, force: {force_check})")
            return await _async_check_all_prices(max_age_hours, force_check)

    try:
        return asyncio.run(run())
    except Exception as e:
        logger.exception(f"Error in check_all_watchlist_prices: {str(e)}")
        raise self.retry(exc=e, countdown=300, max_retries=3)


async def _async_check_all_prices(max_age_hours: int, force_check: bool):
    """Async implementation of check_all_prices"""
    try:
        start_time = datetime.now(timezone.utc)

        async with celery_session_scope() as session:
            if force_check:
                # Get ALL watchlist items
                stmt = select(Watchlist).order_by(Watchlist.updated_at.asc())
                result = await session.execute(stmt)
                items_to_check = result.scalars().all()
            else:
                # Get items that need checking based on age using the fixed service method
                items_to_check = await WatchlistService.get_items_needing_price_check(
                    session, max_age_hours=max_age_hours
                )

            if not items_to_check:
                logger.info("✅ No watchlist items need price checking")
                return {
                    "status": "completed",
                    "items_checked": 0,
                    "alerts_created": 0,
                    "items_with_errors": 0,
                    "duration_seconds": 0,
                }

            logger.info(f"📋 Found {len(items_to_check)} watchlist items to check")

            # Process items in batches to avoid overwhelming the system
            batch_size = 10
            items_queued = 0
            items_with_errors = 0

            for i in range(0, len(items_to_check), batch_size):
                batch = items_to_check[i : i + batch_size]
                batch_num = i // batch_size + 1
                total_batches = (len(items_to_check) - 1) // batch_size + 1

                logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} items)")

                # Queue individual check tasks for better error isolation
                for item in batch:
                    try:
                        check_single_watchlist_item.delay(item.id, include_mtgstocks=True, retry_on_error=True)
                        items_queued += 1

                    except Exception as e:
                        logger.error(f"❌ Error queuing check for {item.card_name}: {str(e)}")
                        items_with_errors += 1

                # Rate limiting between batches
                if i + batch_size < len(items_to_check):
                    await asyncio.sleep(1)

            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()

            result = {
                "status": "completed",
                "items_queued": items_queued,
                "items_with_errors": items_with_errors,
                "total_items": len(items_to_check),
                "duration_seconds": duration,
                "batch_size": batch_size,
            }

            logger.info(
                f"✅ Price check cycle completed in {duration:.1f}s - "
                f"Queued: {items_queued}/{len(items_to_check)}, Errors: {items_with_errors}"
            )

            return result

    except Exception as e:
        logger.error(f"❌ Error in price check cycle: {str(e)}")
        raise


@celery_app.task(bind=True, base=CallbackTask, name="watchlist.check_single_item")
def check_single_watchlist_item(self, watchlist_id: int, include_mtgstocks: bool = True, retry_on_error: bool = True):
    """
    Check prices for a single watchlist item

    Args:
        watchlist_id: ID of the watchlist item to check
        include_mtgstocks: Whether to fetch MTGStocks price data
        retry_on_error: Whether to retry on failure
    """

    async def run():
        app = create_app()
        async with app.app_context():
            return await _async_check_single_item(watchlist_id, include_mtgstocks)

    try:
        return asyncio.run(run())
    except Exception as e:
        logger.error(f"❌ Error checking watchlist item {watchlist_id}: {str(e)}")
        if retry_on_error:
            # Exponential backoff: 1min, 5min, 15min
            countdown = min(60 * (2**self.request.retries), 900)  # Cap at 15 minutes
            raise self.retry(exc=e, countdown=countdown, max_retries=3)
        else:
            raise


async def _async_check_single_item(watchlist_id: int, include_mtgstocks: bool):
    """Async implementation of check_single_item"""
    try:
        async with celery_session_scope() as session:
            # Get the watchlist item
            watchlist_item = await session.get(Watchlist, watchlist_id)
            if not watchlist_item:
                logger.warning(f"Watchlist item {watchlist_id} not found")
                return {"status": "not_found", "watchlist_id": watchlist_id}

            logger.info(f"🔍 Checking prices for {watchlist_item.card_name}")

            # Get market price if requested
            market_price = None
            if include_mtgstocks and watchlist_item.mtgstocks_id:
                try:
                    market_price = await get_mtgstocks_price(watchlist_item.mtgstocks_id)
                    if market_price:
                        logger.debug(f"Got MTGStocks price: ${market_price} for {watchlist_item.card_name}")
                except Exception as e:
                    logger.warning(f"Failed to get MTGStocks price for {watchlist_item.card_name}: {str(e)}")

            # Check prices and create alerts using the service
            alerts = await WatchlistService.check_prices_for_watchlist_item(session, watchlist_item, market_price)

            await session.commit()

            result = {
                "status": "completed",
                "watchlist_id": watchlist_id,
                "card_name": watchlist_item.card_name,
                "alerts_created": len(alerts),
                "market_price": float(market_price) if market_price else None,
                "alerts": [alert.to_dict() for alert in alerts] if alerts else [],
            }

            if alerts:
                logger.info(f"🔔 Created {len(alerts)} alert(s) for {watchlist_item.card_name}")
            else:
                logger.debug(f"No alerts created for {watchlist_item.card_name}")

            return result

    except Exception as e:
        logger.error(f"❌ Error checking watchlist item {watchlist_id}: {str(e)}")
        raise


@celery_app.task(bind=True, base=CallbackTask, name="watchlist.cleanup_old_alerts")
def cleanup_old_price_alerts(self, days_to_keep: int = 30):
    """
    Clean up old price alerts to prevent database bloat

    Args:
        days_to_keep: Number of days of alerts to keep
    """

    async def run():
        app = create_app()
        async with app.app_context():
            logger.info(f"🧹 Starting cleanup of alerts older than {days_to_keep} days")
            return await _async_cleanup_alerts(days_to_keep)

    try:
        return asyncio.run(run())
    except Exception as e:
        logger.error(f"❌ Error cleaning up alerts: {str(e)}")
        raise self.retry(exc=e, countdown=3600, max_retries=2)


async def _async_cleanup_alerts(days_to_keep: int):
    """Async implementation of cleanup_alerts"""
    try:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)
        logger.info(f"🧹 Cleaning up price alerts older than {cutoff_date}")

        async with celery_session_scope() as session:
            # Delete old alerts
            stmt = delete(PriceAlert).where(PriceAlert.created_at < cutoff_date)
            result = await session.execute(stmt)
            deleted_count = result.rowcount or 0

            await session.commit()

            logger.info(f"✅ Cleaned up {deleted_count} old price alerts")
            return {"status": "completed", "deleted_count": deleted_count}

    except Exception as e:
        logger.error(f"❌ Error cleaning up alerts: {str(e)}")
        raise


@celery_app.task(bind=True, base=CallbackTask, name="watchlist.update_mtgstocks_prices")
def update_mtgstocks_prices_for_watchlist(self, batch_size: int = 5):
    """
    Update MTGStocks prices for watchlist items that have MTGStocks IDs

    Args:
        batch_size: Number of items to process in each batch
    """

    async def run():
        app = create_app()
        async with app.app_context():
            logger.info("🏪 Starting MTGStocks price update")
            return await _async_update_mtgstocks_prices(batch_size)

    try:
        return asyncio.run(run())
    except Exception as e:
        logger.error(f"❌ Error updating MTGStocks prices: {str(e)}")
        raise self.retry(exc=e, countdown=1800, max_retries=2)


async def _async_update_mtgstocks_prices(batch_size: int):
    """Async implementation of update_mtgstocks_prices"""
    try:
        async with celery_session_scope() as session:
            # Get watchlist items that have MTGStocks IDs
            stmt = select(Watchlist).where(Watchlist.mtgstocks_id.is_not(None)).order_by(Watchlist.updated_at.asc())
            result = await session.execute(stmt)
            items_with_mtgstocks = result.scalars().all()

            if not items_with_mtgstocks:
                logger.info("No watchlist items with MTGStocks IDs found")
                return {"status": "completed", "items_processed": 0}

            logger.info(f"Found {len(items_with_mtgstocks)} items with MTGStocks IDs")

            updated_count = 0
            error_count = 0

            # Use the MTGStocks service for better rate limiting and error handling
            async with MTGStocksService() as mtg_service:
                # Process in batches to respect rate limits
                for i in range(0, len(items_with_mtgstocks), batch_size):
                    batch = items_with_mtgstocks[i : i + batch_size]
                    batch_num = i // batch_size + 1
                    total_batches = (len(items_with_mtgstocks) - 1) // batch_size + 1

                    logger.info(f"Processing MTGStocks batch {batch_num}/{total_batches}")

                    for item in batch:
                        try:
                            # Get current MTGStocks price using the service
                            market_price = await mtg_service.get_market_price(item.mtgstocks_id)

                            if market_price:
                                # Update the item's updated_at to track when we last checked MTGStocks
                                item.updated_at = datetime.now(timezone.utc)
                                updated_count += 1

                                # Queue a price check for this item now that we have market price
                                check_single_watchlist_item.delay(
                                    item.id, include_mtgstocks=False, retry_on_error=True  # We already have the price
                                )

                        except Exception as e:
                            logger.error(f"Error updating MTGStocks price for {item.card_name}: {str(e)}")
                            error_count += 1

                    # Rate limiting: 3 second delay between batches (handled by service)
                    if i + batch_size < len(items_with_mtgstocks):
                        await asyncio.sleep(3)

            await session.commit()

            result = {
                "status": "completed",
                "items_processed": updated_count,
                "items_with_errors": error_count,
                "total_items": len(items_with_mtgstocks),
            }

            logger.info(f"✅ MTGStocks update completed - Processed: {updated_count}, Errors: {error_count}")
            return result

    except Exception as e:
        logger.error(f"❌ Error updating MTGStocks prices: {str(e)}")
        raise


@celery_app.task(bind=True, base=CallbackTask, name="watchlist.auto_link_mtgstocks")
def auto_link_missing_mtgstocks_data(self, batch_size: int = 5):
    """
    Automatically find and link MTGStocks data for watchlist items that don't have it

    Args:
        batch_size: Number of items to process in each batch
    """

    async def run():
        app = create_app()
        async with app.app_context():
            logger.info("🔗 Starting auto-link of missing MTGStocks data")
            return await _async_auto_link_mtgstocks(batch_size)

    try:
        return asyncio.run(run())
    except Exception as e:
        logger.error(f"❌ Error in auto-link MTGStocks: {str(e)}")
        raise self.retry(exc=e, countdown=1800, max_retries=2)


async def _async_auto_link_mtgstocks(batch_size: int):
    """Async implementation of auto_link_mtgstocks"""
    try:
        async with celery_session_scope() as session:
            # Get watchlist items that don't have MTGStocks IDs
            stmt = select(Watchlist).where(Watchlist.mtgstocks_id.is_(None)).order_by(Watchlist.created_at.asc())
            result = await session.execute(stmt)
            items_without_mtgstocks = result.scalars().all()

            if not items_without_mtgstocks:
                logger.info("No watchlist items without MTGStocks IDs found")
                return {"status": "completed", "items_processed": 0, "items_linked": 0}

            logger.info(f"Found {len(items_without_mtgstocks)} items without MTGStocks IDs")

            linked_count = 0
            error_count = 0

            async with MTGStocksService() as mtg_service:
                # Process in batches
                for i in range(0, len(items_without_mtgstocks), batch_size):
                    batch = items_without_mtgstocks[i : i + batch_size]
                    batch_num = i // batch_size + 1
                    total_batches = (len(items_without_mtgstocks) - 1) // batch_size + 1

                    logger.info(f"Processing auto-link batch {batch_num}/{total_batches}")

                    for item in batch:
                        try:
                            # Search for the card
                            card_data = await mtg_service.search_and_get_best_match(item.card_name, item.set_code)

                            if card_data and card_data.get("id"):
                                # Update the watchlist item
                                item.mtgstocks_id = card_data["id"]
                                item.mtgstocks_url = card_data.get("url")
                                item.updated_at = datetime.now(timezone.utc)

                                linked_count += 1
                                logger.info(f"Auto-linked {item.card_name} to MTGStocks ID {card_data['id']}")

                                # Queue a price check for this newly linked item
                                check_single_watchlist_item.delay(item.id, include_mtgstocks=True, retry_on_error=False)

                        except Exception as e:
                            logger.error(f"Error auto-linking {item.card_name}: {str(e)}")
                            error_count += 1

                    # Rate limiting between batches
                    if i + batch_size < len(items_without_mtgstocks):
                        await asyncio.sleep(5)  # Longer delay for search operations

            await session.commit()

            result = {
                "status": "completed",
                "items_processed": len(items_without_mtgstocks),
                "items_linked": linked_count,
                "items_with_errors": error_count,
            }

            logger.info(f"✅ Auto-link completed - Linked: {linked_count}, Errors: {error_count}")
            return result

    except Exception as e:
        logger.error(f"❌ Error in auto-link MTGStocks: {str(e)}")
        raise


@celery_app.task(bind=True, base=CallbackTask, name="watchlist.manual_check_user_watchlist")
def manual_check_user_watchlist(self, user_id: int):
    """
    Manually check all watchlist items for a specific user

    Args:
        user_id: ID of the user whose watchlist to check
    """

    async def run():
        app = create_app()
        async with app.app_context():
            logger.info(f"🔄 Starting manual watchlist check for user {user_id}")
            return await _async_manual_check_user(user_id)

    try:
        return asyncio.run(run())
    except Exception as e:
        logger.error(f"❌ Error in manual check for user {user_id}: {str(e)}")
        return {"status": "error", "error": str(e)}


async def _async_manual_check_user(user_id: int):
    """Async implementation of manual_check_user"""
    try:
        async with celery_session_scope() as session:
            # Get all watchlist items for the user using the service
            user_items = await WatchlistService.get_user_watchlist(session, user_id)

            if not user_items:
                logger.info(f"No watchlist items found for user {user_id}")
                return {"status": "completed", "items_checked": 0, "alerts_created": 0}

            logger.info(f"Found {len(user_items)} watchlist items for user {user_id}")

            items_queued = 0

            # Queue individual checks for each item
            for item in user_items:
                try:
                    # Queue the check task
                    check_single_watchlist_item.delay(
                        item.id, include_mtgstocks=True, retry_on_error=False  # Don't retry for manual checks
                    )
                    items_queued += 1

                except Exception as e:
                    logger.error(f"Error queuing check for {item.card_name}: {str(e)}")

            return {
                "status": "completed",
                "user_id": user_id,
                "items_queued": items_queued,
                "message": f"Queued price checks for {items_queued} watchlist items",
            }

    except Exception as e:
        logger.error(f"❌ Error in manual check for user {user_id}: {str(e)}")
        raise


@celery_app.task(bind=True, base=CallbackTask, name="watchlist.refresh_cache")
def refresh_watchlist_cache(self):
    """Refresh any watchlist-related caches"""

    async def run():
        app = create_app()
        async with app.app_context():
            logger.info("🔄 Refreshing watchlist caches...")
            return await _async_refresh_watchlist_cache()

    try:
        return asyncio.run(run())
    except Exception as e:
        logger.error(f"Watchlist cache refresh error: {e}")
        return {"status": "error", "error": str(e)}


async def _async_refresh_watchlist_cache():
    """Async implementation of cache refresh"""
    try:
        async with celery_session_scope() as session:
            # Refresh any cached statistics or precomputed values
            # This could include:
            # - User watchlist counts
            # - Popular cards being watched
            # - Market trend data

            logger.info("✅ Watchlist cache refresh completed")
            return {"status": "completed", "refreshed_at": datetime.now(timezone.utc).isoformat()}

    except Exception as e:
        logger.error(f"Error refreshing watchlist cache: {str(e)}")
        raise


# Health check task
@celery_app.task(bind=True, base=CallbackTask, name="watchlist.health_check")
def watchlist_health_check(self):
    """Perform health check on watchlist system"""

    async def run():
        app = create_app()
        async with app.app_context():
            return await _async_health_check()

    try:
        return asyncio.run(run())
    except Exception as e:
        logger.error(f"Watchlist health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}


async def _async_health_check():
    """Check the health of the watchlist system"""
    try:
        async with celery_session_scope() as session:
            # Check database connectivity
            stmt = select(func.count(Watchlist.id))
            result = await session.execute(stmt)
            total_items = result.scalar()

            # Check MTGStocks connectivity
            mtgstocks_healthy = False
            try:
                async with MTGStocksService() as mtg_service:
                    test_results = await mtg_service.search_cards("Lightning Bolt", limit=1)
                    mtgstocks_healthy = len(test_results) > 0
            except Exception as e:
                logger.warning(f"MTGStocks health check failed: {str(e)}")

            # Check for stuck scan statuses
            from app.models.watchlist import WatchlistScanStatus

            cutoff = datetime.now(timezone.utc) - timedelta(hours=6)

            stuck_stmt = select(func.count(WatchlistScanStatus.id)).where(
                and_(WatchlistScanStatus.consecutive_errors >= 3, WatchlistScanStatus.last_scanned < cutoff)
            )
            stuck_result = await session.execute(stuck_stmt)
            stuck_items = stuck_result.scalar()

            return {
                "status": "healthy" if mtgstocks_healthy else "degraded",
                "total_watchlist_items": total_items,
                "stuck_items": stuck_items,
                "mtgstocks_healthy": mtgstocks_healthy,
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }

    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
