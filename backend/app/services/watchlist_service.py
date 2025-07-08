import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from decimal import Decimal

from sqlalchemy import select, and_, or_, func, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.watchlist import Watchlist, PriceAlert, WatchlistScanStatus
from app.services.mtgstocks_service import MTGStocksService, search_mtgstocks_cards
from app.models.scan import ScanResult

logger = logging.getLogger(__name__)


class WatchlistService:
    """Service for managing watchlist operations"""

    @staticmethod
    async def get_items_needing_price_check(session: AsyncSession, max_age_hours: int = 1) -> List[Watchlist]:
        """
        Get watchlist items that need price checking based on age

        Args:
            session: Database session
            max_age_hours: Check items not scanned in this many hours

        Returns:
            List of Watchlist items that need checking
        """
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)

            # Query for items that either:
            # 1. Have never been scanned (no scan_status record)
            # 2. Haven't been scanned since cutoff_time
            # 3. Had consecutive errors and should be retried

            # Subquery to get latest scan status for each watchlist item
            latest_scan_subq = (
                select(
                    WatchlistScanStatus.watchlist_id,
                    func.max(WatchlistScanStatus.last_scanned).label("last_scanned"),
                    WatchlistScanStatus.consecutive_errors,
                )
                .group_by(WatchlistScanStatus.watchlist_id)
                .subquery()
            )

            # Main query
            stmt = (
                select(Watchlist)
                .outerjoin(latest_scan_subq, Watchlist.id == latest_scan_subq.c.watchlist_id)
                .where(
                    or_(
                        # Never scanned
                        latest_scan_subq.c.last_scanned.is_(None),
                        # Not scanned recently
                        latest_scan_subq.c.last_scanned < cutoff_time,
                        # Had errors but should retry (< 3 consecutive errors)
                        and_(latest_scan_subq.c.consecutive_errors < 3, latest_scan_subq.c.last_scanned < cutoff_time),
                    )
                )
                .order_by(
                    func.isnull(latest_scan_subq.c.last_scanned).desc(),  # NULLs first
                    latest_scan_subq.c.last_scanned.asc(),  # Then by timestamp
                    Watchlist.created_at.asc(),  # Finally by creation
                )
            )

            result = await session.execute(stmt)
            items = result.scalars().all()

            logger.info(f"Found {len(items)} watchlist items needing price check")
            return items

        except Exception as e:
            logger.error(f"Error getting items needing price check: {str(e)}")
            # Fallback to getting all items if query fails
            stmt = select(Watchlist).order_by(Watchlist.updated_at.asc())
            result = await session.execute(stmt)
            return result.scalars().all()

    @staticmethod
    async def check_prices_for_watchlist_item(
        session: AsyncSession, watchlist_item: Watchlist, market_price: Optional[Decimal] = None
    ) -> List[PriceAlert]:
        """
        Check prices for a watchlist item and create alerts if needed

        Args:
            session: Database session
            watchlist_item: The watchlist item to check
            market_price: Current market price from MTGStocks (optional)

        Returns:
            List of created price alerts
        """
        try:
            alerts_created = []

            # Get recent scan results for this card
            scan_results = await WatchlistService._get_recent_scan_results(session, watchlist_item)

            if not scan_results:
                logger.debug(f"No recent scan results found for {watchlist_item.card_name}")
                await WatchlistService._update_scan_status(session, watchlist_item, success=True)
                return alerts_created

            # Find the best price from scan results
            best_result = min(scan_results, key=lambda x: x.price)

            # Check if we should create alerts
            should_alert, alert_type = await WatchlistService._should_create_alert(
                watchlist_item, best_result, market_price
            )

            if should_alert:
                # Create price alert
                alert = PriceAlert(
                    watchlist_id=watchlist_item.id,
                    site_name=best_result.site_name,
                    current_price=best_result.price,
                    market_price=market_price,
                    price_difference=(market_price - best_result.price if market_price else None),
                    percentage_difference=(
                        ((market_price - best_result.price) / market_price * 100)
                        if market_price and market_price > 0
                        else None
                    ),
                    alert_type=alert_type,
                    scan_result_id=best_result.id,
                    is_viewed=False,
                )

                session.add(alert)
                alerts_created.append(alert)

                logger.info(
                    f"Created {alert_type} alert for {watchlist_item.card_name}: "
                    f"${best_result.price} at {best_result.site_name}"
                )

            # Update scan status
            await WatchlistService._update_scan_status(session, watchlist_item, success=True)

            return alerts_created

        except Exception as e:
            logger.error(f"Error checking prices for {watchlist_item.card_name}: {str(e)}")
            await WatchlistService._update_scan_status(session, watchlist_item, success=False, error=str(e))
            raise

    @staticmethod
    async def _get_recent_scan_results(
        session: AsyncSession, watchlist_item: Watchlist, hours_back: int = 24
    ) -> List[ScanResult]:
        """Get recent scan results for a watchlist item"""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_back)

        # Build card name variations for matching
        card_variations = [
            watchlist_item.card_name,
            watchlist_item.card_name.lower(),
            watchlist_item.card_name.replace("'", "'"),  # Handle apostrophe variations
            watchlist_item.card_name.replace("'", ""),  # Remove apostrophes
        ]

        stmt = select(ScanResult).where(
            and_(
                ScanResult.updated_at >= cutoff_time,  # FIXED: Use updated_at instead of created_at
                or_(
                    *[ScanResult.name.ilike(f"%{variation}%") for variation in card_variations]
                ),  # FIXED: Use .name instead of .card_name
            )
        )

        # Add set code filter if available
        if watchlist_item.set_code:
            stmt = stmt.where(
                or_(
                    ScanResult.set_code == watchlist_item.set_code,
                    ScanResult.set_code.is_(None),  # Include results without set code
                )
            )

        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def _should_create_alert(
        watchlist_item: Watchlist, best_result: ScanResult, market_price: Optional[Decimal]
    ) -> tuple[bool, str]:
        """
        Determine if we should create an alert and what type

        Returns:
            (should_alert: bool, alert_type: str)
        """
        # Check target price alert
        if watchlist_item.target_price and best_result.price <= watchlist_item.target_price:
            return True, "target_reached"

        # Check good deal alert (significantly below market price)
        if market_price and market_price > 0:
            discount_percentage = ((market_price - best_result.price) / market_price) * 100

            # Alert if price is 15% or more below market price
            if discount_percentage >= 15:
                return True, "good_deal"

        # Check for significant price drops (compared to previous alerts)
        # This would require comparing with recent alerts - simplified for now
        return True, "price_drop"  # Always create alerts for price tracking

    @staticmethod
    async def _update_scan_status(
        session: AsyncSession, watchlist_item: Watchlist, success: bool, error: Optional[str] = None
    ):
        """Update or create scan status for a watchlist item"""
        try:
            # Try to get existing scan status
            stmt = select(WatchlistScanStatus).where(WatchlistScanStatus.watchlist_id == watchlist_item.id)
            result = await session.execute(stmt)
            scan_status = result.scalar_one_or_none()

            if scan_status:
                # Update existing status
                scan_status.last_scanned = datetime.now(timezone.utc)
                scan_status.scan_count += 1

                if success:
                    scan_status.consecutive_errors = 0
                    scan_status.last_error = None
                else:
                    scan_status.consecutive_errors += 1
                    scan_status.last_error = error
            else:
                # Create new scan status
                scan_status = WatchlistScanStatus(
                    watchlist_id=watchlist_item.id,
                    last_scanned=datetime.now(timezone.utc),
                    scan_count=1,
                    consecutive_errors=0 if success else 1,
                    last_error=None if success else error,
                )
                session.add(scan_status)

        except Exception as e:
            logger.error(f"Error updating scan status: {str(e)}")

    ############################################################################################################
    # Watchlist Operations
    ############################################################################################################

    @staticmethod
    async def get_user_watchlist(session: AsyncSession, user_id: int) -> List[Watchlist]:
        """Get all watchlist items for a user with latest price data"""
        try:
            # Eager load the price_alerts relationship
            stmt = (
                select(Watchlist)
                .options(selectinload(Watchlist.price_alerts))
                .where(Watchlist.user_id == user_id)
                .order_by(Watchlist.created_at.desc())
            )
            result = await session.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting user watchlist: {str(e)}")
            return []

    @staticmethod
    async def create_watchlist_item(
        session: AsyncSession,
        user_id: int,
        card_name: str,
        set_code: Optional[str] = None,
        target_price: Optional[Decimal] = None,
        mtgstocks_id: Optional[int] = None,
        mtgstocks_url: Optional[str] = None,
    ) -> Watchlist:
        """Create a new watchlist item"""
        watchlist_item = Watchlist(
            user_id=user_id,
            card_name=card_name.strip(),
            set_code=set_code.strip() if set_code else None,
            target_price=target_price,
            mtgstocks_id=mtgstocks_id,
            mtgstocks_url=mtgstocks_url,
        )

        session.add(watchlist_item)
        await session.flush()  # Get the ID

        return watchlist_item

    @staticmethod
    async def remove_from_watchlist(session: AsyncSession, watchlist_id: int, user_id: int) -> bool:
        """Remove a watchlist item"""
        stmt = select(Watchlist).where(and_(Watchlist.id == watchlist_id, Watchlist.user_id == user_id))
        result = await session.execute(stmt)
        watchlist_item = result.scalar_one_or_none()

        if watchlist_item:
            await session.delete(watchlist_item)
            return True
        return False

    @staticmethod
    async def delete_watchlist_items(session: AsyncSession, watchlist_ids: List[int], user_id: int):
        """Delete multiple watchlist items"""
        deleted = []
        errors = []

        for watchlist_id in watchlist_ids:
            try:
                success = await WatchlistService.remove_from_watchlist(session, watchlist_id, user_id)
                if success:
                    deleted.append(watchlist_id)
                else:
                    errors.append({"watchlist_id": watchlist_id, "error": "Not found"})
            except Exception as e:
                errors.append({"watchlist_id": watchlist_id, "error": str(e)})

        return deleted, errors

    @staticmethod
    async def update_watchlist_item(session: AsyncSession, watchlist_id: int, user_id: int, **updates):
        """Update a watchlist item"""
        stmt = select(Watchlist).where(and_(Watchlist.id == watchlist_id, Watchlist.user_id == user_id))
        result = await session.execute(stmt)
        watchlist_item = result.scalar_one_or_none()

        if not watchlist_item:
            return None

        # Update allowed fields
        allowed_fields = ["target_price", "set_code", "mtgstocks_id", "mtgstocks_url"]
        for field, value in updates.items():
            if field in allowed_fields:
                setattr(watchlist_item, field, value)

        watchlist_item.updated_at = datetime.now(timezone.utc)
        return watchlist_item

    ############################################################################################################
    # Price Alert Operations
    ############################################################################################################

    @staticmethod
    async def get_recent_alerts(
        session: AsyncSession, user_id: int, hours_back: int = 24, limit: int = 50
    ) -> List[PriceAlert]:
        """Get recent price alerts for a user"""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_back)

        stmt = (
            select(PriceAlert)
            .join(Watchlist)
            .where(and_(Watchlist.user_id == user_id, PriceAlert.created_at >= cutoff_time))
            .order_by(PriceAlert.created_at.desc())
            .limit(limit)
            .options(selectinload(PriceAlert.watchlist_item))
        )

        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def mark_alerts_as_viewed(session: AsyncSession, alert_ids: List[int], user_id: int) -> int:
        """Mark alerts as viewed"""
        from sqlalchemy import update

        stmt = (
            update(PriceAlert)
            .where(and_(PriceAlert.id.in_(alert_ids), PriceAlert.watchlist_item.has(Watchlist.user_id == user_id)))
            .values(is_viewed=True)
        )

        result = await session.execute(stmt)
        return result.rowcount or 0
