from contextlib import contextmanager
import logging
from typing import Optional, List
from app.extensions import db
from app.models.optimization_results import OptimizationResult
from app.models.scan import Scan
from app.dto.optimization_dto import OptimizationResultDTO

logger = logging.getLogger(__name__)

class OptimizationService:
    @contextmanager
    def transaction_context():
        """Context manager for database transactions"""
        try:
            yield
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f"Transaction error: {str(e)}")
            raise
        finally:
            db.session.close()
            
    @staticmethod
    def create_optimization_result(scan_id: int, result_dto: OptimizationResultDTO) -> OptimizationResult:
        """
        Create a new optimization result
        
        Args:
            scan_id: ID of the related scan
            optimization_data: Dictionary containing optimization results
            
        Returns:
            OptimizationResult or None if creation fails
            
        Raises:
            ValueError: If input data is invalid
        """
        
        try:
            """Create a new optimization result"""
            with db.session.begin_nested():  # Use transaction context
                scan = db.session.get(Scan, scan_id)
                if not scan:
                    raise ValueError(f"No scan found with id {scan_id}")

                optimization = OptimizationResult(
                    scan_id=scan_id,
                    status=result_dto.status,
                    message=result_dto.message,
                    sites_scraped=result_dto.sites_scraped,
                    cards_scraped=result_dto.cards_scraped,
                    solutions=[solution.model_dump() for solution in result_dto.solutions],
                    errors=result_dto.errors
                )
                db.session.add(optimization)
                db.session.commit()
                return optimization

        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to create optimization result: {str(e)}")
            raise
    

    @staticmethod
    def get_optimization_results(limit: int = 5) -> List[OptimizationResult]:
        """Get recent optimization results"""
        try:
            results = (OptimizationResult.query
                    .order_by(OptimizationResult.created_at.desc())
                    .limit(limit)
                    .all())  # Make sure we use .all() to get a list
            return results
        except Exception as e:
            logger.error(f"Error fetching optimization results: {str(e)}")
            return []

    @staticmethod
    def get_optimization_results_by_scan(scan_id: int) -> List[OptimizationResult]:
        """Get optimization results for a specific scan"""
        try:
            return OptimizationResult.query.filter_by(scan_id=scan_id).all()
        except Exception as e:
            logger.error(f"Error fetching results for scan {scan_id}: {str(e)}")
            return []  # Consistent empty list return on error

    @staticmethod
    def get_latest_optimization() -> Optional[OptimizationResult]:
        """Get the most recent optimization result"""
        try:
            return OptimizationResult.query.order_by(
                OptimizationResult.created_at.desc()
            ).first()
        except Exception as e:
            logger.error(f"Error fetching latest optimization: {str(e)}")
            return None
