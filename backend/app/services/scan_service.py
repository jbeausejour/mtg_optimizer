from contextlib import contextmanager
from datetime import datetime, timezone
from sqlalchemy.exc import SQLAlchemyError
from app.extensions import db
from app.models.scan import Scan, ScanResult
from app.models.site import Site
import logging

logger = logging.getLogger(__name__)

class ScanService:
    @staticmethod
    @contextmanager
    def transaction_context():
        """Context manager for database transactions"""
        try:
            yield
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Database error: {str(e)}")
            raise
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error in transaction: {str(e)}")
            raise
        finally:
            db.session.close()

    @staticmethod
    def _get_current_time():
        """Return current time in UTC without microseconds"""
        return datetime.now(timezone.utc).replace(microsecond=0)

    @staticmethod
    def create_scan():
        with ScanService.transaction_context():
            scan = Scan(created_at=ScanService._get_current_time())
            db.session.add(scan)
            return scan

    @staticmethod
    def save_scan_result(scan_id, result):
        with ScanService.transaction_context():
            scan_result = ScanResult(
                scan_id=scan_id,
                name=result["name"],
                site_id=result["site_id"],
                price=result["price"],
                set_name=result["set_name"],
                version=result.get("version", "Standard"),
                foil=result.get("foil", False),
                quality=result.get("quality"),
                language=result.get("language", "English"),
                quantity=result.get("quantity", 0),
                updated_at=ScanService._get_current_time()
            )
            db.session.add(scan_result)
            return scan_result

    @staticmethod
    def get_latest_scan_results():
        latest_scan = Scan.query.order_by(Scan.id.desc()).first()
        if not latest_scan:
            return None, None

        # Updated to use new relationship name
        results = db.session.query(
            ScanResult.name,
            ScanResult.price,
            ScanResult.site_id,
            ScanResult.set_name,
            ScanResult.quality,
            ScanResult.foil,
            ScanResult.language,
            ScanResult.quantity,
            Site.name.label('site_name')
        ).join(
            Site, ScanResult.site_id == Site.id
        ).filter(
            ScanResult.scan_id == latest_scan.id
        ).all()

        return latest_scan, results

    @staticmethod
    def update_scan_results(scan_id, results):
        """Update multiple scan results in a single transaction"""
        with ScanService.transaction_context():
            for result in results:
                existing_result = ScanResult.query.filter_by(
                    scan_id=scan_id,
                    name=result["name"],
                    site_id=result["site_id"]
                ).first()

                if existing_result:
                    # Update existing result
                    for key, value in result.items():
                        if hasattr(existing_result, key):
                            setattr(existing_result, key, value)
                else:
                    # Create new result
                    ScanService.save_scan_result(scan_id, result)