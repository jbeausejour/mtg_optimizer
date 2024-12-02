
from app.extensions import db
from app.models.site import Site
import logging

logger = logging.getLogger(__name__)

class SiteService:
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
    def create_site_info(name, site_id, url):
        """Create a lightweight site info object"""
        class SiteInfo:
            def __init__(self, name, site_id, url):
                self.name = name
                self.id = site_id
                self.url = url
        return SiteInfo(name, site_id, url)