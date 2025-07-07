import logging
import asyncio
from typing import Dict, List, Optional, Tuple, Any, Union

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from bs4 import BeautifulSoup
from app.models.site import Site
from app.services.async_base_service import AsyncBaseService
from app.utils.selenium_driver import get_network_driver

logger = logging.getLogger(__name__)


class SiteService(AsyncBaseService[Site]):
    """Async service for site operations"""

    model_class = Site

    # Cache for site details
    site_details_cache = {}

    @classmethod
    async def get_active_sites(cls, session: AsyncSession) -> List[Site]:
        """Get all active sites"""
        try:
            result = await session.execute(select(Site).filter(Site.active == True))
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting active sites: {str(e)}")
            return []

    @classmethod
    async def get_all_sites(cls, session: AsyncSession) -> List[Site]:
        """Get all sites"""
        try:
            return await cls.get_all(session)
        except Exception as e:
            logger.error(f"Error getting all sites: {str(e)}")
            return []

    @classmethod
    async def get_sites_by_ids(cls, session: AsyncSession, site_ids: List[int]) -> List[Site]:
        """Get sites by IDs"""
        try:
            result = await session.execute(select(Site).filter(Site.id.in_(site_ids)))
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting sites by IDs: {str(e)}")
            return []

    @classmethod
    async def get_sites_by_names(cls, session: AsyncSession, site_names: List[str]) -> List[Site]:
        """Get sites by names"""
        try:
            result = await session.execute(select(Site).filter(Site.name.in_(site_names)))
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting sites by names: {str(e)}")
            return []

    @classmethod
    async def add_site(cls, session: AsyncSession, data: Dict[str, Any]) -> Optional[Site]:
        """Add a new site"""
        try:
            site = await cls.create(session, **data)
            return site
        except Exception as e:
            logger.error(f"Error adding site: {str(e)}")
            return None

    @classmethod
    async def update_site(cls, session: AsyncSession, site_id: int, data: Dict[str, Any]) -> Optional[Site]:
        """Update an existing site"""
        try:
            site = await session.get(Site, site_id)

            if not site:
                raise ValueError("Site not found")

            changes_made = False
            for key, value in data.items():
                if hasattr(site, key) and getattr(site, key) != value:
                    setattr(site, key, value)
                    changes_made = True

            if not changes_made:
                raise ValueError("No changes detected")

            return site
        except IntegrityError:
            logger.error(f"Update failed due to integrity constraint for site {site_id}")
            raise ValueError("Update failed due to integrity constraint")
        except Exception as e:
            logger.error(f"Error updating site {site_id}: {str(e)}")
            raise

    @classmethod
    async def delete_site(cls, session: AsyncSession, site_id: int) -> bool:
        """Delete a site"""
        try:
            result = await cls.delete(session, site_id)

            return result
        except Exception as e:
            logger.error(f"Error deleting site {site_id}: {str(e)}")
            return False

    @classmethod
    async def delete_sites_by_ids(cls, session: AsyncSession, site_ids: List[int]) -> int:
        """Bulk delete sites by a list of IDs"""
        try:
            result = await session.execute(cls.delete(Site).where(Site.id.in_(site_ids)))
            return result.rowcount or 0
        except Exception as e:
            logger.error(f"Error bulk deleting sites: {str(e)}")
            raise

    @classmethod
    async def init_site_details_cache_async(
        cls, session: AsyncSession, site_ids: List[int]
    ) -> Dict[int, Tuple[str, Dict[str, str]]]:
        """Initialize the site details cache for multiple sites"""
        try:
            sites = await cls.get_sites_by_ids(session, site_ids)
            results = {}

            for site in sites:
                site_data = {
                    "id": site.id,
                    "name": site.name,
                    "method": site.method,
                    "url": site.url,
                    "api_url": site.api_url,
                }

                auth_token, headers = await cls.init_site_details_cache(site_data)
                cls.site_details_cache[site.id] = (auth_token, headers)
                results[site.id] = (auth_token, headers)

            return results
        except Exception as e:
            logger.error(f"Error initializing site details cache: {str(e)}")
            return {}

    @classmethod
    async def init_site_details_cache(cls, site_data: Dict[str, Any]) -> Tuple[Optional[str], Dict[str, str]]:
        """Initialize site details cache for a single site using site_data dict"""
        site_id = site_data["id"]
        site_name = site_data["name"]
        site_method = site_data["method"]
        site_url = site_data["url"]
        site_api_url = site_data.get("api_url")

        network_driver = get_network_driver()
        try:
            # Handle f2f differently
            if site_method == "f2f":
                headers = {
                    "Content-Type": "application/json",
                    "Accept": "*/*",
                    "Origin": "https://www.facetofacegames.com",
                    "Referer": "https://www.facetofacegames.com/pages/deck-builder",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Connection": "keep-alive",
                }

                cls.site_details_cache[site_id] = (None, headers)
                return None, headers

            # For other site types
            search_url = site_url.rstrip("/")
            initial_response = await network_driver.fetch_url(search_url)
            if not initial_response or not initial_response.get("content"):
                logger.error(f"Initial request failed for {site_name}")

                # Return default headers as fallback
                default_headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                    "Content-Type": "application/x-www-form-urlencoded",
                }

                return None, default_headers

            soup = BeautifulSoup(initial_response["content"], "html.parser")
            auth_token = None

            if site_method.lower() != "shopify":
                auth_token = await network_driver.get_auth_token(soup, site_data)
                if not auth_token:
                    logger.info(f"Failed to get auth token for {site_name}")

            site_details = initial_response.get("site_details", {})
            headers = site_details.get("headers", {})
            relevant_headers = {
                key: value
                for key, value in headers.items()
                if key.lower() in ["cache-control", "content-type", "accept-language", "accept-encoding"]
            }

            cookies = site_details.get("cookies", {})
            cookie_str = "; ".join([f"{key}={value}" for key, value in cookies.items()]) if cookies else ""

            if site_method == "shopify":
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

            cls.site_details_cache[site_id] = (auth_token, relevant_headers)
            return auth_token, relevant_headers

        except Exception as e:
            logger.error(f"Error initializing site details cache for {site_name}: {str(e)}", exc_info=True)

            # Return default headers as fallback
            default_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Content-Type": "application/x-www-form-urlencoded",
            }

            return None, default_headers
        finally:
            # Ensure the network driver is closed properly
            if network_driver and hasattr(network_driver, "close"):
                await network_driver.close()

    @classmethod
    async def get_site_details_async(cls, site_data: Dict[str, Any]) -> Tuple[Optional[str], Dict[str, str]]:
        """Get site details from cache or initialize if not present"""
        site_id = site_data["id"]
        site_name = site_data["name"]

        # Check cache first
        if site_id in cls.site_details_cache:
            logger.info(f"Using cached details for site {site_name}")
            return cls.site_details_cache[site_id]

        # logger.warning(f"[CACHE MISS] Site details cache miss for {site_name} (ID: {site_id}), initializing now.")
        # logger.info(f"[CACHE DEBUG] Current keys in site_details_cache: {list(cls.site_details_cache.keys())}")
        return await cls.init_site_details_cache(site_data)
