from contextlib import contextmanager
from sqlalchemy.exc import SQLAlchemyError
from app.extensions import db
from app.models.site import Site
from sqlalchemy.exc import IntegrityError
import logging

logger = logging.getLogger(__name__)

class SiteService:
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
    def get_sites_by_ids(site_ids):
        """Get sites by their IDs"""
        try:
            sites = Site.query.filter(Site.id.in_(site_ids)).all()
            return sites
        except Exception as e:
            logger.error(f"Error getting sites by IDs: {str(e)}")
            return []

    @staticmethod
    def get_site_data(sites):
        """Convert site objects to dictionary with necessary data"""
        try:
            return {
                site.name: {
                    'id': site.id,
                    'url': site.url,
                    'name': site.name
                } for site in sites
            }
        except Exception as e:
            logger.error(f"Error converting sites to data dict: {str(e)}")
            return {}

    @staticmethod
    def get_active_sites():
        """Get all active sites"""
        return Site.query.filter_by(active=True).all()

    @staticmethod
    def get_all_sites():
        return Site.query.all()

    @staticmethod
    def add_site(data):
        new_site = Site(**data)
        db.session.add(new_site)
        db.session.commit()
        return new_site

    @staticmethod
    def update_site(site_id, data):
        site = Site.query.get(site_id)
        if not site:
            raise ValueError("Site not found")

        changes_made = False
        for key, value in data.items():
            if hasattr(site, key) and getattr(site, key) != value:
                setattr(site, key, value)
                changes_made = True

        if changes_made:
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                raise ValueError("Update failed due to integrity constraint")
        else:
            raise ValueError("No changes detected")

        return site

    @staticmethod
    def create_site_info(name, site_id, url):
        """Create a lightweight site info object"""
        class SiteInfo:
            def __init__(self, name, site_id, url):
                self.name = name
                self.id = site_id
                self.url = url
        return SiteInfo(name, site_id, url)