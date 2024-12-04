from contextlib import contextmanager
from datetime import datetime, timezone
from sqlalchemy.exc import SQLAlchemyError
from app.extensions import db
from app.models.scan import Scan, ScanResult
from app.services.site_service import SiteService
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
        """Create and persist a new scan"""
        try:
            scan = Scan()
            db.session.add(scan)
            db.session.flush()  # Get the ID without committing
            scan_id = scan.id   # Store the ID
            db.session.commit() # Now commit
            return scan_id  # Return just the ID instead of the scan object
        except Exception as e:
            logger.error(f"Error creating scan: {str(e)}")
            db.session.rollback()
            raise

    @staticmethod
    def get_scan_by_id(scan_id):
        """Get a scan by ID, ensuring it's attached to the current session"""
        return db.session.get(Scan, scan_id)

    @staticmethod
    def save_scan_result(scan_id, result):
        """Save a single scan result"""
        with ScanService.transaction_context():
            # Verify scan exists and is attached to session
            scan = db.session.get(Scan, scan_id)
            if not scan:
                raise ValueError(f"No scan found with id {scan_id}")

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

        # Use SiteService to get site names
        results = db.session.query(
            ScanResult.name,
            ScanResult.price,
            ScanResult.site_id,
            ScanResult.set_name,
            ScanResult.quality,
            ScanResult.foil,
            ScanResult.language,
            ScanResult.quantity
        ).filter(
            ScanResult.scan_id == latest_scan.id
        ).all()

        # Convert results to include site names
        if results:
            sites = SiteService.get_sites_by_ids([r.site_id for r in results])
            site_map = {site.id: site.name for site in sites}
            results_with_sites = [
                (*r[:-1], site_map.get(r.site_id, 'Unknown Site'))
                for r in results
            ]
            return latest_scan, results_with_sites

        return latest_scan, []

    # Scan Operations
    @staticmethod
    def get_scan_results(scan_id):
        scan = db.session.get(Scan, scan_id)
        if not scan:
            return None
        return scan

    @staticmethod
    def get_all_scan_results(limit=5):
        return Scan.query.order_by(Scan.created_at.desc()).limit(limit).all()
