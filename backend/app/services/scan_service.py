import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Tuple

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.scan import Scan, ScanResult
from app.models.site import Site
from app.services.async_base_service import AsyncBaseService

logger = logging.getLogger(__name__)


class ScanService(AsyncBaseService[Scan]):
    """Async service for scan operations"""

    model_class = Scan

    @staticmethod
    def _get_current_time():
        """Return current time in UTC without microseconds"""
        return datetime.now(timezone.utc).replace(microsecond=0)

    @classmethod
    async def create_scan(cls, session: AsyncSession, buylist_id: int) -> int:
        """Create and persist a new scan"""
        try:
            scan = await cls.create(session, buylist_id=buylist_id)
            # ensures other workers can access it
            return scan.id
        except Exception as e:
            logger.error(f"Error creating scan: {str(e)}")
            raise

    @classmethod
    async def delete_scans(cls, session: AsyncSession, scan_ids: List[int]) -> Tuple[List[int], List[Dict]]:
        """
        Deletes scans by their IDs.

        Returns:
        - deleted: List of successfully deleted scan IDs
        - errors: List of {scan_id, error} dicts
        """
        deleted = []
        errors = []

        for scan_id in scan_ids:
            try:
                scan = await session.get(Scan, scan_id)
                if not scan:
                    logger.warning(f"[delete_scans] Scan ID {scan_id} not found.")
                    errors.append({"scan_id": scan_id, "error": "Not found"})
                    continue

                await cls.delete_object(session, scan)
                logger.info(f"[delete_scans] Deleted Scan ID {scan_id}.")
                deleted.append(scan_id)

            except Exception as e:
                logger.error(f"[delete_scans] Error deleting scan ID {scan_id}: {str(e)}")
                errors.append({"scan_id": scan_id, "error": str(e)})

        return deleted, errors

    @classmethod
    async def get_all_scans(cls, session: AsyncSession) -> List[Scan]:
        """Get all scans ordered by creation date with preloaded scan_results"""
        try:
            result = await session.execute(
                select(Scan).options(selectinload(Scan.scan_results)).order_by(Scan.created_at.desc())
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting all scans: {str(e)}")
            return []

    @classmethod
    async def create_scan_result(cls, session: AsyncSession, scan_id: int, card_result: Dict[str, Any]) -> ScanResult:
        """Save a single scan result"""
        try:
            # Verify scan exists
            scan = await session.get(Scan, scan_id)
            if not scan:
                raise ValueError(f"No scan found with id {scan_id}")

            scan_result = ScanResult(
                scan_id=scan_id,
                name=card_result["name"],
                price=card_result["price"],
                site_id=card_result["site_id"],
                set_name=card_result["set_name"],
                set_code=card_result["set_code"],
                version=card_result.get("version"),
                foil=card_result.get("foil", False),
                quality=card_result.get("quality"),
                language=card_result.get("language", "English"),
                quantity=card_result.get("quantity", 0),
                variant_id=card_result.get("variant_id"),
                updated_at=datetime.now(timezone.utc),
            )
            session.add(scan_result)
            return scan_result
        except Exception as e:

            await session.rollback()
            logger.error(f"Error creating scan result: {str(e)}")
            raise

    @classmethod
    async def get_scan_results_by_id_and_sites(
        cls, session: AsyncSession, scan_id: int, site_ids: List[int]
    ) -> List[ScanResult]:
        """Get scan results by scan ID and site IDs"""
        try:
            result = await session.execute(
                select(ScanResult).filter(ScanResult.scan_id == scan_id).filter(ScanResult.site_id.in_(site_ids))
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting scan results by ID and sites: {str(e)}")
            return []

    @classmethod
    async def get_latest_scan_results(cls, session: AsyncSession):
        """Get latest scan results with site names"""
        try:
            # Get the latest scan
            result = await session.execute(select(Scan).order_by(Scan.id.desc()).limit(1))
            latest_scan = result.scalars().first()

            if not latest_scan:
                return None, None

            # Get scan results
            results_query = await session.execute(
                select(
                    ScanResult.name,
                    ScanResult.price,
                    ScanResult.site_id,
                    ScanResult.set_name,
                    ScanResult.quality,
                    ScanResult.foil,
                    ScanResult.language,
                    ScanResult.quantity,
                    ScanResult.updated_at,
                ).filter(ScanResult.scan_id == latest_scan.id)
            )
            results = results_query.all()

            # Get site names
            if results:
                site_ids = [r.site_id for r in results]
                sites_query = await session.execute(select(Site).filter(Site.id.in_(site_ids)))
                sites = sites_query.scalars().all()
                site_map = {site.id: site.name for site in sites}

                # Format results with site names
                results_with_sites = [(*r[:-1], site_map.get(r.site_id, "Unknown Site")) for r in results]
                return latest_scan, results_with_sites

            return latest_scan, []
        except Exception as e:
            logger.error(f"Error getting latest scan results: {str(e)}")
            return None, None

    @classmethod
    async def get_latest_scan_results_by_site_and_cards(
        cls, session: AsyncSession, fresh_cards: List[str], site_ids: List[int]
    ) -> List[ScanResult]:
        """
        Get latest scan results for multiple cards.
        Uses window functions to efficiently get the most recent entry per card.
        """
        try:
            # This approach uses a CTE (Common Table Expression) for better performance with async SQLAlchemy
            latest_scans_cte = (
                select(ScanResult.name, ScanResult.site_id, func.max(ScanResult.updated_at).label("max_updated_at"))
                .filter(and_(ScanResult.name.in_(fresh_cards), ScanResult.site_id.in_(site_ids)))
                .group_by(ScanResult.name, ScanResult.site_id)
                .cte("latest_scans")
            )

            result = await session.execute(
                select(ScanResult)
                .join(
                    latest_scans_cte,
                    and_(
                        ScanResult.name == latest_scans_cte.c.name,
                        ScanResult.site_id == latest_scans_cte.c.site_id,
                        ScanResult.updated_at == latest_scans_cte.c.max_updated_at,
                    ),
                )
                .options(selectinload(ScanResult.site))  # <== this line ensures site is fetched eagerly
            )

            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting latest scan results by site and cards: {str(e)}")
            return []

    @classmethod
    async def get_latest_scan_updated_at_by_card_name(cls, session: AsyncSession, card_name: str) -> Optional[datetime]:
        """Get only the updated_at timestamp for a specific card, safely detached from session"""
        try:
            result = await session.execute(
                select(ScanResult.updated_at)
                .filter(ScanResult.name == card_name)
                .order_by(ScanResult.updated_at.desc())
                .limit(1)
            )
            updated_at = result.scalar_one_or_none()
            return updated_at.replace(tzinfo=timezone.utc, microsecond=0) if updated_at else None
        except Exception as e:
            logger.error(f"Error getting updated_at for {card_name}: {str(e)}")
            return None

    @classmethod
    async def get_scan_results_by_scan_id(cls, session: AsyncSession, scan_id: int) -> List[ScanResult]:
        try:
            stmt = (
                select(Scan)
                .options(
                    selectinload(Scan.scan_results),
                    selectinload(Scan.optimization_result),
                )
                .filter(Scan.id == scan_id)
            )
            result = await session.execute(stmt)
            return result.scalars().first()
        except Exception as e:
            logger.error(f"Error fetching full scan by ID: {str(e)}")
            return None
