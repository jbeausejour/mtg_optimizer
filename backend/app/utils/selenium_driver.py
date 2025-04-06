import asyncio
import logging
import json
import re
import time
from typing import Optional, Union
from urllib.parse import urlparse

import aiohttp
from aiohttp import ClientTimeout, TCPConnector

logger = logging.getLogger(__name__)


class MethodRateLimiter:
    def __init__(self):
        # Store semaphores for concurrency control (limits parallel requests)
        self.limiters = {}
        # Store last request time per method
        self.last_request_time = {}
        # Store accumulated tokens per method
        self.tokens = {}
        # Store the event loop that created this limiter
        self._loop = None

    def get_concurrency(self, method) -> int:
        """Optimal concurrency levels for stability"""
        method = method.lower()
        return {
            "crystal": 6,  # moderately high, usually stable
            "scrapper": 6,  # similar to crystal
            "f2f": 2,  # lower concurrency for f2f API (sensitive to burst requests)
            "shopify": 4,  # Shopify/Binder tends to throttle heavily, keep lower
        }.get(method, 4)

    def get_rate_limit(self, method) -> float:
        """Optimal rate limits for stability"""
        method = method.lower()
        return {
            "crystal": 1.5,  # ~1.5 req/sec is safe and stable
            "scrapper": 1.5,
            "f2f": 0.35,  # 0.5 req/sec (1 request every 2 seconds) more reliable
            "shopify": 0.5,  # Shopify/Binder safe rate is around 1 req/sec
        }.get(method, 1.0)

    def get_limiter(self, method) -> asyncio.Semaphore:
        """Get or create a semaphore for this method type"""
        method = method.lower()

        # Always get the current event loop
        current_loop = asyncio.get_event_loop()

        # If we don't have a stored loop or the limiter hasn't been created yet,
        # store the current loop and create the limiters
        if self._loop is None:
            self._loop = current_loop
        elif self._loop != current_loop:
            # If we detect a different event loop, recreate all limiters
            logger.warning("Different event loop detected - recreating rate limiters")
            self.limiters = {}
            self._loop = current_loop

        if method not in self.limiters:
            concurrency = self.get_concurrency(method)
            self.limiters[method] = asyncio.Semaphore(concurrency)

        return self.limiters[method]

    async def acquire(self, method):
        """Acquire both a semaphore slot and respect the rate limit"""
        method = method.lower()

        # Get the appropriate semaphore
        limiter = self.get_limiter(method)

        # First wait for semaphore (limits concurrent requests)
        await limiter.acquire()

        # Then enforce rate limit (requests per second)
        rate_limit = self.get_rate_limit(method)
        now = time.time()

        # Initialize last request time if not set
        if method not in self.last_request_time:
            self.last_request_time[method] = now
            self.tokens[method] = 1.0

        # Calculate time since last request and add tokens
        time_passed = now - self.last_request_time[method]
        self.tokens[method] += time_passed * rate_limit

        # Cap tokens at max of 1
        if self.tokens[method] > 1.0:
            self.tokens[method] = 1.0

        # If we don't have enough tokens, sleep until we do
        if self.tokens[method] < 1.0:
            sleep_time = (1.0 - self.tokens[method]) / rate_limit
            await asyncio.sleep(sleep_time)
            self.tokens[method] = 0.0
        else:
            # Consume a token
            self.tokens[method] -= 1.0

        # Update last request time
        self.last_request_time[method] = time.time()

        # Return a function to release the semaphore
        def release():
            limiter.release()

        return release


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
        self.method_limiter = MethodRateLimiter()
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

        # Apply both concurrency and rate limiting
        release = await self.method_limiter.acquire(site.method)

        max_retries = 3
        retry_count = 0
        backoff_factor = 1
        wait_time = 1
        semaphore = asyncio.Semaphore(5)

        try:
            async with semaphore:
                while retry_count < max_retries:
                    connection_info = {
                        "attempt": retry_count + 1,
                        "max_retries": max_retries,
                    }  # Initialize with basic info

                    try:
                        retry_count += 1

                        # Enhanced timeout configuration
                        timeout = aiohttp.ClientTimeout(total=100, connect=30, sock_read=60, sock_connect=15)
                        connection_info["timeout"] = str(timeout)

                        # Use a session that will be properly closed
                        session = None
                        response = None

                        try:
                            retry_count += 1
                            # Create a dedicated session for this request
                            session = aiohttp.ClientSession(
                                connector=TCPConnector(limit=10, force_close=True, enable_cleanup_closed=True),
                                timeout=timeout,
                                headers=headers,
                            )
                            # Track this session for proper cleanup
                            self._active_sessions.add(session)

                            # Track the start time for detailed timing
                            start_time = time.time()

                            # Make the request
                            if use_json:
                                response = await session.post(url, json=payload, headers=headers, timeout=timeout)
                            else:
                                response = await session.post(url, data=payload, headers=headers, timeout=timeout)

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
                                            "ssl": bool(
                                                response.connection.transport.get_extra_info("ssl_object", None)
                                            ),
                                        }
                                    )

                            logger.debug(f"Connection details for {site.name}: {connection_info}")

                            if response.status == 200:
                                if retry_count > 1:
                                    logger.info(
                                        f"Success posting to {site.name} after {retry_count} attempts in {elapsed_time} seconds"
                                    )
                                else:
                                    logger.info(f"Success posting to {site.name} in {elapsed_time} seconds")

                                return await response.text()

                            elif response.status in (301, 302, 303, 307, 308):
                                redirect_url = response.headers.get("Location")
                                if redirect_url:
                                    logger.info(f"Following redirect to {redirect_url}")
                                    url = redirect_url
                                    continue
                            elif response.status == 404:
                                logger.error(f"URL not found: {url} (Took {elapsed_time} seconds)")
                                return None
                            elif response.status == 401:
                                # logger.error(f"401 received, headers are: {headers_used}")
                                logger.error(f"Response 401 received, response are: {response}")
                                continue
                            elif response.status == 429:
                                wait_time = int(response.headers.get("Retry-After", 60))
                                logger.warning(
                                    f"Rate limited on {site.name}, waiting {wait_time}s (Took {elapsed_time} seconds)"
                                )
                                await asyncio.sleep(wait_time)
                                continue
                            else:
                                logger.error(
                                    f"Error {response.status} from {site.name} (Attempt {retry_count}/{max_retries}) - Took {elapsed_time} seconds"
                                )
                                await asyncio.sleep(wait_time)
                                continue

                        except asyncio.TimeoutError:
                            elapsed_time = round(time.time() - start_time, 2)
                            logger.error(
                                f"Timeout after {elapsed_time:.2f}s posting to {site.name} (Attempt {retry_count}/{max_retries})"
                            )
                            await asyncio.sleep(backoff_factor * (2 ** (retry_count - 1)))
                            continue
                        finally:
                            # Always close the session
                            if session:
                                try:
                                    self._active_sessions.discard(session)
                                    if not session.closed:
                                        await session.close()
                                except Exception as e:
                                    logger.error(f"Error closing session: {str(e)}")

                    except aiohttp.ClientError as e:
                        elapsed_time = round(time.time() - start_time, 2)
                        connection_info["error"] = f"Client error: {str(e)}"
                        logger.error(
                            f"Connection failed to {site.name} (Took {elapsed_time} seconds): {connection_info}"
                        )
                        await asyncio.sleep(backoff_factor)
                        continue

                    except Exception as e:
                        elapsed_time = round(time.time() - start_time, 2)
                        connection_info["error"] = f"Unexpected error: {str(e)}"
                        logger.error(f"Request failed to {site.name} (Took {elapsed_time} seconds): {connection_info}")
                        await asyncio.sleep(backoff_factor)
                        continue

                    backoff_factor *= 2
        finally:
            # Always release the semaphore
            try:
                release()
            except Exception as e:
                logger.error(f"Error releasing semaphore: {str(e)}")

        return None

    async def fetch_url(self, url: str) -> Optional[str]:
        """Enhanced fetch URL with detailed diagnostics and Selenium fallback"""
        await self._ensure_session()

        max_retries = 5
        retry_count = 0
        backoff_factor = 1
        wait_time = 1  # Initialize wait_time here

        while retry_count < max_retries:

            connection_info = {
                "attempt": retry_count + 1,
                "max_retries": max_retries,
            }  # Initialize with basic info

            try:
                retry_count += 1

                # Track start time for detailed timing
                start_time = asyncio.get_event_loop().time()

                # Create a dedicated session for this request that will be properly closed
                session = None
                response = None
                try:
                    # Set timeout and connector with proper configuration
                    timeout = aiohttp.ClientTimeout(total=30, connect=10, sock_read=25, sock_connect=10)
                    connector = TCPConnector(limit=10, force_close=True, enable_cleanup_closed=True)

                    # Create a dedicated session
                    session = aiohttp.ClientSession(connector=connector, timeout=timeout)
                    self._active_sessions.add(session)

                    # Make the request
                    async with session.get(url) as response:
                        elapsed_time = asyncio.get_event_loop().time() - start_time
                        # Extract cookies

                        # Gather detailed connection information
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
                                logger.warning(f"Empty response from {url}, attempting Selenium fallback")
                                logger.info(f"GET connection details for {url}: {connection_info}")

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

                finally:
                    # Always close the session
                    if session:
                        try:
                            self._active_sessions.discard(session)
                            if not session.closed:
                                await session.close()
                        except Exception as e:
                            logger.error(f"Error closing session: {str(e)}")

            except asyncio.TimeoutError:
                elapsed = asyncio.get_event_loop().time() - start_time
                logger.error(f"Timeout after {elapsed:.2f}s fetching {url} (attempt {retry_count}/{max_retries})")
                logger.error(f"Timeout configuration: {timeout}")

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

        logger.warning(f"No auth token found for {site.name}")
        return ""

    async def _fallback_request(self, url: str, payload: str, headers: dict) -> Optional[str]:
        """Fallback request using alternative approach"""
        session = None
        try:
            # Create a new session with different settings
            session = aiohttp.ClientSession(
                timeout=ClientTimeout(total=120),  # Longer timeout
                headers={
                    **headers,
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                },
            )
            self._active_sessions.add(session)

            # First make a GET request to get any necessary tokens
            async with session.get(url) as response:
                if response.status != 200:
                    return None

                # Extract any CSRF tokens if present
                html = await response.text()
                csrf_token = self._extract_csrf_token(html)

                if csrf_token:
                    headers["X-CSRF-Token"] = csrf_token

            # Make the actual POST request
            async with session.post(url, data=payload, headers=headers, allow_redirects=True) as response:
                if response.status == 200:
                    return await response.text()
        except Exception as e:
            logger.error(f"Fallback request failed: {str(e)}")
            return None
        finally:
            # Always close the session
            if session:
                try:
                    self._active_sessions.discard(session)
                    if not session.closed:
                        await session.close()
                except Exception as e:
                    logger.error(f"Error closing fallback session: {str(e)}")

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
