import asyncio
import logging
import json
import re
import time
from typing import Optional, Union
from urllib.parse import urlparse

import aiohttp
from aiohttp import ClientTimeout, TCPConnector
from app.utils.async_context_manager import managed_aiohttp_session

logger = logging.getLogger(__name__)


class NetworkDriver:
    """Enhanced base class for network operations with connection pooling"""

    def __init__(self, max_connections: int = 100, keepalive_timeout: int = 30):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br, zstd",
        }
        self.session = None
        self.connector = None
        self.max_connections = max_connections
        self.keepalive_timeout = keepalive_timeout
        self._default_rate_limit = asyncio.Semaphore(10)
        # Store the event loop that created this driver
        self._loop = None
        # Track active sessions for cleanup
        self._active_sessions = set()

    async def _init_connector(self):
        """Initialize the connector when needed"""
        # Check if we're in the same event loop
        current_loop = asyncio.get_event_loop()
        if self._loop is None:
            self._loop = current_loop
        elif self._loop != current_loop:
            logger.warning("Different event loop detected - recreating connector and session")
            # We're in a different event loop, close existing resources if any
            await self.close()
            self._loop = current_loop

        if self.connector is None:
            self.connector = TCPConnector(
                limit=self.max_connections,
                ttl_dns_cache=300,
                keepalive_timeout=self.keepalive_timeout,
                force_close=False,
                enable_cleanup_closed=True,
            )

    async def _ensure_session(self):
        """Ensure the ClientSession is initialized"""
        await self._init_connector()  # This will handle event loop checking

        if not self.session or self.session.closed:
            self.session = aiohttp.ClientSession(connector=self.connector, headers=self.headers, trust_env=True)

    async def close(self):
        """Explicitly close session and connector"""
        # Close any tracked sessions
        for session in list(self._active_sessions):
            try:
                if not session.closed:
                    await session.close()
                self._active_sessions.remove(session)
            except Exception as e:
                logger.error(f"Error closing tracked session: {str(e)}")

        # Close the main session
        if self.session and not self.session.closed:
            try:
                await self.session.close()
                await asyncio.sleep(0.25)
            except Exception as e:
                logger.error(f"Error closing main session: {str(e)}")
            finally:
                self.session = None

        # Close the connector
        if self.connector and not self.connector.closed:
            try:
                await self.connector.close()
            except Exception as e:
                logger.error(f"Error closing connector: {str(e)}")
            finally:
                self.connector = None

    async def __aenter__(self):
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def post_request(
        self, url: str, payload: Union[dict, str, list], headers: dict = None, site: any = None, use_json=False
    ) -> Optional[str]:
        """Enhanced POST request with detailed error tracking and Selenium fallback"""
        await self._ensure_session()

        max_retries = 3
        retry_count = 0
        backoff_factor = 1
        # wait_time = 1
        # semaphore = asyncio.Semaphore(5)

        # async with semaphore:
        while retry_count < max_retries:
            connection_info = {
                "attempt": retry_count + 1,
                "max_retries": max_retries,
            }  # Initialize with basic info

            start_time = time.time()  # Start timing
            retry_count += 1
            try:
                retry_count += 1

                # Enhanced timeout configuration
                timeout = aiohttp.ClientTimeout(total=100, connect=30, sock_read=60, sock_connect=15)
                connection_info["timeout"] = str(timeout)

                # Create session factory function for the context manager
                def create_session():
                    return aiohttp.ClientSession(
                        connector=TCPConnector(limit=10, force_close=True, enable_cleanup_closed=True),
                        timeout=timeout,
                        headers=headers,
                    )

                # Use the managed_aiohttp_session context manager
                async with managed_aiohttp_session(create_session, name=f"{site['name']}-request") as session:
                    # Make the request
                    if use_json:
                        async with session.post(url, json=payload, headers=headers, timeout=timeout) as response:
                            return await self._handle_response(
                                response, retry_count, connection_info, url, site, start_time
                            )
                    else:
                        async with session.post(url, data=payload, headers=headers, timeout=timeout) as response:
                            return await self._handle_response(
                                response, retry_count, connection_info, url, site, start_time
                            )

            except asyncio.TimeoutError:
                elapsed_time = round(time.time() - start_time, 2)
                logger.error(
                    f"Timeout after {elapsed_time:.2f}s posting to {site['name']} (Attempt {retry_count}/{max_retries})"
                )
                await asyncio.sleep(backoff_factor * (2 ** (retry_count - 1)))
                continue

            except aiohttp.ClientError as e:
                elapsed_time = round(time.time() - start_time, 2)
                connection_info["error"] = f"Client error: {str(e)}"
                logger.error(f"Connection failed to {site['name']} (Took {elapsed_time} seconds): {connection_info}")
                await asyncio.sleep(backoff_factor)
                continue

            except Exception as e:
                elapsed_time = round(time.time() - start_time, 2)
                connection_info["error"] = f"Unexpected error: {str(e)}"
                logger.error(f"Request failed to {site['name']} (Took {elapsed_time} seconds): {connection_info}")
                await asyncio.sleep(backoff_factor)
                continue

            backoff_factor *= 2

        return None

    async def _handle_response(self, response, retry_count, connection_info, url, site, start_time):
        """Handle the response from a request"""
        elapsed_time = round(time.time() - start_time, 2)  # Compute elapsed time

        connection_info.update(
            {
                "status": response.status,
                "elapsed_time": f"{elapsed_time:.2f}s",
                "headers": dict(response.headers),
            }
        )

        # Log extra connection details
        if hasattr(response, "connection") and response.connection:
            if hasattr(response.connection, "transport") and response.connection.transport:
                connection_info.update(
                    {
                        "peername": response.connection.transport.get_extra_info("peername", "N/A"),
                        "ssl": bool(response.connection.transport.get_extra_info("ssl_object", None)),
                    }
                )

        logger.debug(f"Connection details for {site['name']}: {connection_info}")

        if response.status == 200:
            # if retry_count > 1:
            #     logger.info(f"Success posting to {site['name']} after {retry_count} attempts in {elapsed_time} seconds")
            # else:
            #     logger.info(f"Success posting to {site['name']} in {elapsed_time} seconds")

            return await response.text()

        elif response.status in (301, 302, 303, 307, 308):
            redirect_url = response.headers.get("Location")
            if redirect_url:
                logger.info(f"Following redirect to {redirect_url}")
                # Return None to trigger the retry with the new URL
                return None

        elif response.status == 404:
            logger.error(f"URL not found: {url} (Took {elapsed_time} seconds)")
            return None

        elif response.status == 401:
            logger.error(f"Response 401 received from {site['name']}")
            return None

        elif response.status == 429:
            wait_time = int(response.headers.get("Retry-After", 60))
            logger.warning(f"Rate limited on {site['name']}, waiting {wait_time}s (Took {elapsed_time} seconds)")
            await asyncio.sleep(wait_time)
            return None

        else:
            logger.error(f"Error {response.status} from {site['name']} (Took {elapsed_time} seconds)")
            return None

    async def fetch_url(self, url: str) -> Optional[str]:
        """Enhanced fetch URL with managed session handling"""
        await self._ensure_session()

        max_retries = 5
        retry_count = 0
        backoff_factor = 1
        wait_time = 1

        while retry_count < max_retries:
            connection_info = {
                "attempt": retry_count + 1,
                "max_retries": max_retries,
            }

            retry_count += 1
            start_time = asyncio.get_event_loop().time()

            try:
                # Set timeout and connector configuration
                timeout = aiohttp.ClientTimeout(total=30, connect=10, sock_read=25, sock_connect=10)

                # Create session factory function
                def create_session():
                    return aiohttp.ClientSession(
                        connector=TCPConnector(limit=10, force_close=True, enable_cleanup_closed=True),
                        timeout=timeout,
                    )

                # Use the managed_aiohttp_session context manager
                async with managed_aiohttp_session(create_session, name=f"fetch-{url[:30]}") as session:
                    async with session.get(url) as response:
                        elapsed_time = asyncio.get_event_loop().time() - start_time

                        # Collect site-specific details
                        site_details = {
                            "status": response.status,
                            "headers": response.headers,
                            "elapsed_time": elapsed_time,
                        }

                        if response.status == 200:
                            content = await response.text()
                            if retry_count > 1:
                                logger.info(f"Successfully fetched {url} after {retry_count} attempts")

                            # Check if content is valid
                            if not content or content.isspace():
                                logger.warning(f"Empty response from {url}")

                            return {
                                "content": content,
                                "site_details": site_details,
                            }

                        elif response.status == 404:
                            logger.error(f"URL not found: {url}")
                            return None

                        elif response.status == 429:  # Rate limit
                            wait_time = int(response.headers.get("Retry-After", 60))
                            logger.warning(f"Rate limited on {url}, waiting {wait_time}s")
                            await asyncio.sleep(wait_time)
                            continue

                        else:
                            logger.error(f"Error response from {url} (attempt {retry_count}/{max_retries})")
                            await asyncio.sleep(wait_time)
                            continue

            except asyncio.TimeoutError:
                elapsed = asyncio.get_event_loop().time() - start_time
                logger.error(f"Timeout after {elapsed:.2f}s fetching {url} (attempt {retry_count}/{max_retries})")
                wait_time = backoff_factor * (2 ** (retry_count - 1))
                await asyncio.sleep(wait_time)

            except aiohttp.ClientError as e:
                logger.error(f"Client error fetching {url} (attempt {retry_count}/{max_retries}):")
                logger.error(f"Error type: {type(e).__name__}")
                logger.error(f"Error details: {str(e)}")
                await asyncio.sleep(backoff_factor * (2 ** (retry_count - 1)))
                continue

            except Exception as e:
                logger.error(f"Unexpected error fetching {url} (attempt {retry_count}/{max_retries}):")
                logger.error(f"Error type: {type(e).__name__}")
                logger.error(f"Error details: {str(e)}")
                await asyncio.sleep(backoff_factor * (2 ** (retry_count - 1)))
                continue

            backoff_factor *= 2

        return None

    async def get_auth_token(self, soup, site):
        """Get authentication token from response"""
        token = None

        # Try multiple methods to find token
        selectors = [
            ("input", {"name": ["authenticity_token", "csrf_token", "_token"]}),
            ("meta", {"name": ["csrf-token", "csrf-param"]}),
            (
                "form input",
                {
                    "type": "hidden",
                    "name": ["authenticity_token", "csrf_token", "_token"],
                },
            ),
        ]

        for tag, attrs in selectors:
            if tag == "form input":
                form = soup.find("form", {"class": ["search-form", "advanced-search", "bulk-search"]})
                if form:
                    element = form.find("input", attrs)
            else:
                element = soup.find(tag, attrs)

            if element:
                token = element.get("value") or element.get("content")
                if token:
                    return token

        # Fallback to script parsing
        scripts = soup.find_all("script", string=re.compile(r"csrf|token|auth"))
        for script in scripts:
            if script.string:
                patterns = [
                    r'csrf_token["\s:]+"([^"]+)"',
                    r'authenticity_token["\s:]+"([^"]+)"',
                    r'_token["\s:]+"([^"]+)"',
                ]
                for pattern in patterns:
                    match = re.search(pattern, script.string)
                    if match:
                        return match.group(1)

        logger.warning(f"No auth token found for {site['name']}")
        return ""

    # async def _fallback_request(self, url: str, payload: str, headers: dict) -> Optional[str]:
    #     """Fallback request using alternative approach"""
    #     session = None
    #     try:
    #         # Create a new session with different settings
    #         session = aiohttp.ClientSession(
    #             timeout=ClientTimeout(total=120),  # Longer timeout
    #             headers={
    #                 **headers,
    #                 "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    #             },
    #         )
    #         self._active_sessions.add(session)

    #         # First make a GET request to get any necessary tokens
    #         async with session.get(url) as response:
    #             if response.status != 200:
    #                 return None

    #             # Extract any CSRF tokens if present
    #             html = await response.text()
    #             csrf_token = self._extract_csrf_token(html)

    #             if csrf_token:
    #                 headers["X-CSRF-Token"] = csrf_token

    #         # Make the actual POST request
    #         async with session.post(url, data=payload, headers=headers, allow_redirects=True) as response:
    #             if response.status == 200:
    #                 return await response.text()
    #     except Exception as e:
    #         logger.error(f"Fallback request failed: {str(e)}")
    #         return None
    #     finally:
    #         # Always close the session
    #         if session:
    #             try:
    #                 self._active_sessions.discard(session)
    #                 if not session.closed:
    #                     await session.close()
    #             except Exception as e:
    #                 logger.error(f"Error closing fallback session: {str(e)}")

    @staticmethod
    def _extract_csrf_token(html: str) -> Optional[str]:
        """Extract CSRF token from HTML content"""
        import re

        # Common patterns for CSRF tokens
        patterns = [
            r'<meta name="csrf-token" content="([^"]+)"',
            r'<input[^>]+name="authenticity_token"[^>]+value="([^"]+)"',
            r'csrf_token["\s:]+"([^"]+)"',
        ]

        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                return match.group(1)

        return None


# Instead of a global instance, provide a factory function
def get_network_driver():
    """Factory function to create a new NetworkDriver instance"""
    return NetworkDriver()
