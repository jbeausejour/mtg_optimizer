import logging
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.dto.optimization_dto import OptimizationResultDTO
from app.models.optimization_results import OptimizationResult
from app.models.scan import Scan
from app.models.buylist import UserBuylist
from app.services.async_base_service import AsyncBaseService

logger = logging.getLogger(__name__)


class OptimizationService(AsyncBaseService[OptimizationResult]):
    """Async service for optimization operations"""

    model_class = OptimizationResult

    @classmethod
    async def create_optimization_result(
        cls, session: AsyncSession, scan_id: int, result_dto: OptimizationResultDTO
    ) -> OptimizationResult:
        """
        Create a new optimization result
        """
        try:
            # Fetch scan asynchronously
            scan_result = await session.execute(select(Scan).where(Scan.id == scan_id))
            scan = scan_result.scalars().first()

            if not scan:
                raise ValueError(f"No scan found with id {scan_id}")
            # Create optimization result
            new_result = await cls.create(
                session,
                **{
                    "scan_id": scan_id,
                    "status": result_dto.status,
                    "message": result_dto.message,
                    "sites_scraped": result_dto.sites_scraped,
                    "cards_scraped": result_dto.cards_scraped,
                    "solutions": [solution.model_dump() for solution in result_dto.solutions],
                    "errors": result_dto.errors,
                },
            )
            return new_result

        except Exception as e:
            logger.error(f"Failed to create optimization result: {str(e)}")
            raise

    @classmethod
    async def get_optimization_results(cls, session: AsyncSession) -> List[OptimizationResult]:
        """Get recent optimization results with related scan and buylist data"""
        try:
            stmt = (
                select(OptimizationResult, Scan, UserBuylist)
                .join(Scan, OptimizationResult.scan_id == Scan.id)
                .outerjoin(UserBuylist, Scan.buylist_id == UserBuylist.id)
                .order_by(OptimizationResult.created_at.desc())
            )

            result = await session.execute(stmt)
            return result.all()
        except Exception as e:
            logger.error(f"Error fetching optimization results: {str(e)}")
            return []

    @classmethod
    async def get_optimization_results_by_scan(cls, session: AsyncSession, scan_id: int) -> List[OptimizationResult]:
        """Get optimization results for a specific scan"""
        try:
            result = await session.execute(select(OptimizationResult).filter(OptimizationResult.scan_id == scan_id))
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error fetching results for scan {scan_id}: {str(e)}")
            return []

    @classmethod
    async def get_latest_optimization(cls, session: AsyncSession) -> Optional[OptimizationResult]:
        """Get the most recent optimization result"""
        try:
            result = await session.execute(
                select(OptimizationResult).order_by(OptimizationResult.created_at.desc()).limit(1)
            )
            return result.scalars().first()
        except Exception as e:
            logger.error(f"Error fetching latest optimization: {str(e)}")
            return None
