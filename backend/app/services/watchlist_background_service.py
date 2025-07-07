import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional
from decimal import Decimal

from app.services.watchlist_service import WatchlistService
from app.utils.async_context_manager import flask_session_scope

logger = logging.getLogger(__name__)


class WatchlistBackgroundService:
    """Background service for automated watchlist price checking"""
    
    def __init__(self, check_interval_minutes: int = 30):
        self.check_interval_minutes = check_interval_minutes
        self.is_running = False
        self.task = None
        
    async def start(self):
        """Start the background price checking service"""
        if self.is_running:
            logger.warning("Watchlist background service is already running")
            return
            
        self.is_running = True
        logger.info(f"Starting watchlist background service (check interval: {self.check_interval_minutes} minutes)")
        
        # Start the background task
        self.task = asyncio.create_task(self._background_loop())
        
    async def stop(self):
        """Stop the background price checking service"""
        if not self.is_running:
            logger.warning("Watchlist background service is not running")
            return
            
        self.is_running = False
        
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            
        logger.info("Watchlist background service stopped")
        
    async def _background_loop(self):
        """Main background loop for price checking"""
        try:
            # Run an initial check
            await self._run_price_check()
            
            # Then run checks at regular intervals
            while self.is_running:
                await asyncio.sleep(self.check_interval_minutes * 60)
                if self.is_running:  # Check again in case we were stopped during sleep
                    await self._run_price_check()
                    
        except asyncio.CancelledError:
            logger.info("Background service task was cancelled")
            raise
        except Exception as e:
            logger.error(f"Error in background service loop: {str(e)}")
            self.is_running = False
            
    async def _run_price_check(self):
        """Run a single price checking cycle"""
        try:
            start_time = datetime.now(timezone.utc)
            logger.info("🔍 Starting watchlist price check cycle")
            
            async with flask_session_scope() as session:
                # Get all items that need price checking (not checked in last hour)
                try:
                    items_to_check = await WatchlistService.get_items_needing_price_check(session, max_age_hours=1)
                except Exception as e:
                    logger.error(f"Error getting items needing price check: {str(e)}")
                    # Fallback to getting all active items
                    from sqlalchemy import select
                    from app.models.watchlist import Watchlist
                    stmt = select(Watchlist).where(Watchlist.is_active == True)
                    result = await session.execute(stmt)
                    items_to_check = result.scalars().all()
                
                if not items_to_check:
                    logger.info("✅ No watchlist items need price checking")
                    return
                
                logger.info(f"📋 Found {len(items_to_check)} watchlist items to check")
                
                total_alerts_created = 0
                items_checked = 0
                items_with_errors = 0
                
                for item in items_to_check:
                    try:
                        # Add delay between items to be respectful to external APIs
                        if items_checked > 0:
                            await asyncio.sleep(2)  # 2 second delay between items
                        
                        # Get market price if available (placeholder for MTGStocks integration)
                        market_price = await self._get_market_price(item)
                        
                        # Check prices and create alerts
                        alerts = await WatchlistService.check_prices_for_watchlist_item(
                            session, item, market_price
                        )
                        
                        total_alerts_created += len(alerts)
                        items_checked += 1
                        
                        if alerts:
                            logger.info(f"🔔 Created {len(alerts)} alert(s) for {item.card_name}")
                        
                    except Exception as e:
                        logger.error(f"❌ Error checking prices for {item.card_name}: {str(e)}")
                        items_with_errors += 1
                        continue
                
                # Commit all changes
                await session.commit()
                
                end_time = datetime.now(timezone.utc)
                duration = (end_time - start_time).total_seconds()
                
                logger.info(
                    f"✅ Price check cycle completed in {duration:.1f}s - "
                    f"Checked: {items_checked}, Alerts: {total_alerts_created}, Errors: {items_with_errors}"
                )
                
        except Exception as e:
            logger.error(f"❌ Error in price check cycle: {str(e)}")
            
    async def _get_market_price(self, watchlist_item) -> Optional[Decimal]:
        """Get market price for a watchlist item (placeholder for MTGStocks integration)"""
        try:
            # This is where you would integrate with MTGStocks or other price APIs
            # For now, return None as placeholder
            
            # Example implementation:
            # if watchlist_item.mtgstocks_id:
            #     price_data = await mtgstocks_service.get_price(watchlist_item.mtgstocks_id)
            #     return Decimal(str(price_data.market_price))
            
            return None
        except Exception as e:
            logger.error(f"Error getting market price for {watchlist_item.card_name}: {str(e)}")
            return None
            
    async def manual_check_all(self):
        """Manually trigger a full price check for all active watchlist items"""
        try:
            logger.info("🔄 Manual price check triggered for all watchlist items")
            
            async with flask_session_scope() as session:
                # Get ALL active watchlist items regardless of last check time
                from sqlalchemy import select, and_
                from app.models.watchlist import Watchlist
                
                stmt = select(Watchlist).where(Watchlist.is_active == True)
                result = await session.execute(stmt)
                all_items = result.scalars().all()
                
                if not all_items:
                    logger.info("No active watchlist items found")
                    return {"items_checked": 0, "alerts_created": 0}
                
                logger.info(f"Checking prices for {len(all_items)} watchlist items")
                
                total_alerts_created = 0
                items_checked = 0
                
                for item in all_items:
                    try:
                        # Add delay between items
                        if items_checked > 0:
                            await asyncio.sleep(1)
                        
                        market_price = await self._get_market_price(item)
                        alerts = await WatchlistService.check_prices_for_watchlist_item(
                            session, item, market_price
                        )
                        
                        total_alerts_created += len(alerts)
                        items_checked += 1
                        
                    except Exception as e:
                        logger.error(f"Error in manual check for {item.card_name}: {str(e)}")
                        continue
                
                await session.commit()
                
                logger.info(f"Manual check completed - Items: {items_checked}, Alerts: {total_alerts_created}")
                return {"items_checked": items_checked, "alerts_created": total_alerts_created}
                
        except Exception as e:
            logger.error(f"Error in manual check all: {str(e)}")
            return {"error": str(e)}


# Global instance
watchlist_background_service = WatchlistBackgroundService()


async def start_watchlist_background_service():
    """Helper function to start the background service"""
    await watchlist_background_service.start()


async def stop_watchlist_background_service():
    """Helper function to stop the background service"""
    await watchlist_background_service.stop()


# Additional route for manual triggering (to be added to your main app)
async def manual_trigger_price_check():
    """Manually trigger a price check cycle"""
    return await watchlist_background_service.manual_check_all()