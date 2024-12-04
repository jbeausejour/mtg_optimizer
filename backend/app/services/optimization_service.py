import logging
from app.extensions import db
from app.models.optimization_results import OptimizationResult
from app.models.scan import Scan

logger = logging.getLogger(__name__)

class OptimizationService:
    @staticmethod
    def create_optimization_result(scan_id, optimization_data):
        """Create a new optimization result"""
        try:
            # Verify scan exists
            scan = db.session.get(Scan, scan_id)
            if not scan:
                raise ValueError(f"No scan found with id {scan_id}")

            optimization = OptimizationResult(
                scan_id=scan_id,
                status=optimization_data['status'],
                message=optimization_data['message'],
                sites_scraped=optimization_data['sites_scraped'],
                cards_scraped=optimization_data['cards_scraped'],
                solutions=optimization_data['optimization']['solutions'],
                errors=optimization_data['optimization']['errors']
            )
            db.session.add(optimization)
            db.session.commit()
            return optimization
        except Exception as e:
            logger.error(f"Error creating optimization result: {str(e)}")
            db.session.rollback()
            raise

    @staticmethod
    def get_optimization_results(limit=5):
        """Get recent optimization results with their scans"""
        try:
            return (db.session.query(Scan, OptimizationResult)
                    .join(OptimizationResult)
                    .order_by(OptimizationResult.created_at.desc())
                    .limit(limit)
                    .all())
        except Exception as e:
            logger.error(f"Error fetching optimization results: {str(e)}")
            return []

    @staticmethod
    def get_optimization_results_by_scan(scan_id):
        """Get optimization results for a specific scan"""
        try:
            return (OptimizationResult.query
                   .filter_by(scan_id=scan_id)
                   .order_by(OptimizationResult.created_at.desc())
                   .all())
        except Exception as e:
            logger.error(f"Error fetching optimization results for scan {scan_id}: {str(e)}")
            return []

    @staticmethod
    def get_latest_optimization_by_scan(scan_id):
        """Get the most recent optimization result for a scan"""
        try:
            return (OptimizationResult.query
                   .filter_by(scan_id=scan_id)
                   .order_by(OptimizationResult.created_at.desc())
                   .first())
        except Exception as e:
            logger.error(f"Error fetching latest optimization result for scan {scan_id}: {str(e)}")
            return None

    @staticmethod
    def get_all_scans_with_optimization():
        """Get all scans with their latest optimization results"""
        try:
            latest_opt = (db.session.query(
                OptimizationResult.scan_id,
                db.func.max(OptimizationResult.created_at).label('max_date')
            )
            .group_by(OptimizationResult.scan_id)
            .subquery())

            return (db.session.query(Scan, OptimizationResult)
                   .join(latest_opt, Scan.id == latest_opt.c.scan_id)
                   .join(OptimizationResult,
                        db.and_(
                            OptimizationResult.scan_id == latest_opt.c.scan_id,
                            OptimizationResult.created_at == latest_opt.c.max_date
                        ))
                   .order_by(Scan.created_at.desc())
                   .all())
        except Exception as e:
            logger.error(f"Error fetching scans with optimization results: {str(e)}")
            return []

    @staticmethod
    def get_latest_optimization():
        """Get the most recent optimization result"""
        return OptimizationResult.query.order_by(OptimizationResult.created_at.desc()).first()