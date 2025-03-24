import asyncio
import logging
from contextlib import contextmanager

from app.extensions import db
from app.models.site import Site
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from bs4 import BeautifulSoup
from app.utils.selenium_driver import network

logger = logging.getLogger(__name__)


class SiteService:

    site_details_cache = {}

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
    def get_sites_by_names(site_names):
        """Get sites by their IDs"""
        try:
            sites = Site.query.filter(Site.name.in_(site_names)).all()
            return sites
        except Exception as e:
            logger.error(f"Error getting sites by IDs: {str(e)}")
            return []

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
    def delete_site(site_id):
        site = Site.query.get(site_id)
        if not site:
            raise ValueError("Site not found")

        db.session.delete(site)
        db.session.commit()
        return site

    @staticmethod
    async def init_site_details_cache(site):
        try:
            if site.method == "f2f":
                headers = {
                    "Content-Type": "application/json",
                    "Accept": "*/*",
                    "Origin": "https://www.facetofacegames.com",
                    "Referer": "https://www.facetofacegames.com/pages/deck-builder",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Connection": "keep-alive",
                }

                SiteService.site_details_cache[site.name] = (None, headers)
                return None, headers

            search_url = site.url.rstrip("/")
            initial_response = await network.fetch_url(search_url)
            if not initial_response or not initial_response.get("content"):
                logger.error(f"Initial request failed for {site.name}")
                return None

            soup = BeautifulSoup(initial_response["content"], "html.parser")
            auth_token = None
            if site.method.lower() != "shopify":
                auth_token = await network.get_auth_token(soup, site)
                if not auth_token:
                    logger.info(f"Failed to get auth token for {site.name}")

            site_details = initial_response.get("site_details", {})
            headers = site_details.get("headers", {})
            relevant_headers = {
                key: value
                for key, value in headers.items()
                if key.lower() in ["cache-control", "content-type", "accept-language", "accept-encoding"]
            }

            cookies = site_details.get("cookies", {})
            cookie_str = "; ".join([f"{key}={value}" for key, value in cookies.items()]) if cookies else ""
            if site.method == "shopify":
                relevant_headers.update(
                    {
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                        "Cookie": cookie_str,
                    }
                )
            else:
                relevant_headers.update(
                    {
                        "Content-Type": "application/x-www-form-urlencoded",
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                        "Cookie": cookie_str,
                    }
                )

            SiteService.site_details_cache[site.name] = (auth_token, relevant_headers)
            return auth_token, relevant_headers

        except Exception as e:
            logger.error(f"Error initializing site details cache for {site.name}: {str(e)}", exc_info=True)
            return None

    @staticmethod
    def get_site_details_sync(site):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(SiteService.get_site_details(site))

    @staticmethod
    async def get_site_details(site):
        if site.name in SiteService.site_details_cache:
            return SiteService.site_details_cache[site.name]
        logger.warning(f"Site details cache miss for {site.name}, initializing now.")
        return await SiteService.init_site_details_cache(site)
