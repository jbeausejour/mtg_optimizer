import logging
import asyncio
from typing import Optional, Union
import aiohttp
from aiohttp import TCPConnector, ClientTimeout
from urllib.parse import urlparse
from fake_useragent import UserAgent
import re

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
        self._rate_limiters = {}
        self._default_rate_limit = asyncio.Semaphore(10)

    async def _init_connector(self):
        """Initialize the connector when needed"""
        if self.connector is None:
            self.connector = TCPConnector(
                limit=self.max_connections,
                ttl_dns_cache=300,
                keepalive_timeout=self.keepalive_timeout,
                force_close=False,
                enable_cleanup_closed=True
            )

    async def _ensure_session(self):
        """Ensure session exists with proper initialization"""
        if not self.session:
            await self._init_connector()
            self.session = aiohttp.ClientSession(
                connector=self.connector,
                headers=self.headers,
                trust_env=True
            )

    async def __aenter__(self):
        await self._ensure_session()
        return self
    
    async def _cleanup(self):
        """Clean up resources"""
        if self.session:
            await self.session.close()
        if self.connector:
            await self.connector.close()
        self.session = None
        self.connector = None

    async def __aexit__(self, exc_type, exc, tb):
        await self._cleanup()
            
    def _get_rate_limiter(self, domain: str) -> asyncio.Semaphore:
        """Get or create rate limiter for a domain"""
        if domain not in self._rate_limiters:
            # Customize rate limits per domain if needed
            if 'example.com' in domain:
                self._rate_limiters[domain] = asyncio.Semaphore(5)  # Stricter limit
            else:
                self._rate_limiters[domain] = self._default_rate_limit
        return self._rate_limiters[domain]
    
    async def post_request(self, url: str, payload: Union[dict, str, list], headers: dict = None) -> Optional[str]:
        """Enhanced POST request with detailed error tracking and Selenium fallback"""
        await self._ensure_session()

        max_retries = 5
        retry_count = 0
        backoff_factor = 1
        wait_time = 1        
        
        while retry_count < max_retries:
            connection_info = {
                'attempt': retry_count + 1,
                'max_retries': max_retries
            }  # Initialize with basic info
            
            try:
                retry_count += 1
                
                # Enhanced timeout configuration
                timeout = aiohttp.ClientTimeout(
                    total=50,
                    connect=15,
                    sock_read=50,
                    sock_connect=10
                )
                connection_info['timeout'] = str(timeout)

                connector = TCPConnector(
                    limit=10,
                    force_close=True,
                    enable_cleanup_closed=True
                )

                # Track the start time for detailed timing
                start_time = asyncio.get_event_loop().time()

                async with aiohttp.ClientSession(
                    connector=connector,
                    timeout=timeout,
                    headers=headers
                ) as session:
                    try:
                        async with session.post(url, data=payload) as response:
                            elapsed_time = asyncio.get_event_loop().time() - start_time
                            
                            # Update connection info with response data
                            connection_info.update({
                                'status': response.status,
                                'elapsed_time': f"{elapsed_time:.2f}s",
                                'headers': dict(response.headers)
                            })
                            
                            # Add transport info if available
                            if hasattr(response, 'connection') and response.connection:
                                if hasattr(response.connection, 'transport') and response.connection.transport:
                                    connection_info.update({
                                        'peername': response.connection.transport.get_extra_info('peername', 'N/A'),
                                        'ssl': bool(response.connection.transport.get_extra_info('ssl_object', None))
                                    })  

                            # Log connection info for debugging
                            logger.debug(f"Connection details for {url}: {connection_info}")

                            if response.status == 200:
                                if retry_count > 1:
                                    logger.info(f"Success posting to {url} after {retry_count} attempts")
                                return await response.text()
                            
                            elif response.status in (301, 302, 303, 307, 308):  # Handle redirects manually if needed
                                redirect_url = response.headers.get('Location')
                                if redirect_url:
                                    logger.info(f"Following redirect to {redirect_url}")
                                    url = redirect_url
                                    continue
                            elif response.status == 404:
                                logger.error(f"URL not found: {url}")
                                return None
                            elif response.status == 429:
                                wait_time = int(response.headers.get('Retry-After', 60))
                                logger.warning(f"Rate limited on {url}, waiting {wait_time}s")
                                await asyncio.sleep(wait_time)
                                continue
                            else:
                                logger.error(f"Error response from {url} (attempt {retry_count}/{max_retries})")
                                logger.error(f"Connection details: {connection_info}")
                                await asyncio.sleep(wait_time)
                                continue
                                
                    except asyncio.TimeoutError:
                        elapsed = asyncio.get_event_loop().time() - start_time
                        logger.error(f"Timeout after {elapsed:.2f}s posting to {url} (attempt {retry_count}/{max_retries})")
                        connection_info['error'] = 'Timeout'
                        #logger.error(f"Request timeout: {connection_info}")
                        await asyncio.sleep(backoff_factor * (2 ** (retry_count - 1)))
                        continue
                        
            except aiohttp.ClientError as e:
                connection_info['error'] = f"Client error: {str(e)}"
                logger.error(f"Connection failed: {connection_info}")
                await asyncio.sleep(backoff_factor)
                continue
                
            except Exception as e:
                connection_info['error'] = f"Unexpected error: {str(e)}"
                logger.error(f"Request failed: {connection_info}")
                await asyncio.sleep(backoff_factor)
                continue
            
            backoff_factor *= 2
        
        return None    
    
    async def fetch_url(self, url: str) -> Optional[str]:
        """Enhanced fetch URL with detailed diagnostics and Selenium fallback"""
        await self._ensure_session()

        max_retries = 5
        retry_count = 0
        backoff_factor = 1
        
        while retry_count < max_retries:

            connection_info = {
                'attempt': retry_count + 1,
                'max_retries': max_retries
            }  # Initialize with basic info
        
            try:
                retry_count += 1
                
                # Track start time for detailed timing
                start_time = asyncio.get_event_loop().time()
                
                # Set timeout and connector with proper configuration
                timeout = aiohttp.ClientTimeout(total=30, connect=10, sock_read=25, sock_connect=10)
                connector = TCPConnector(limit=10, force_close=True, enable_cleanup_closed=True)
                
                async with aiohttp.ClientSession(
                    connector=connector,
                    timeout=timeout
                ) as session:
                    try:
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
                                    
                                return {"content": content, "site_details": site_details}
                                
                            elif response.status == 404:
                                logger.error(f"URL not found: {url}")
                                return None
                                
                            elif response.status == 429:  # Rate limit
                                wait_time = int(response.headers.get('Retry-After', 60))
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
            ("form input", {"type": "hidden", "name": ["authenticity_token", "csrf_token", "_token"]})
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
        scripts = soup.find_all("script", string=re.compile(r'csrf|token|auth'))
        for script in scripts:
            if script.string:
                patterns = [
                    r'csrf_token["\s:]+"([^"]+)"',
                    r'authenticity_token["\s:]+"([^"]+)"',
                    r'_token["\s:]+"([^"]+)"'
                ]
                for pattern in patterns:
                    match = re.search(pattern, script.string)
                    if match:
                        return match.group(1)
                        
        logger.warning(f"No auth token found for {site.name}")
        return ""
        
    async def _fallback_request(self, url: str, payload: str, headers: dict) -> Optional[str]:
        """Fallback request using alternative approach"""
        try:
            # Create a new session with different settings
            async with aiohttp.ClientSession(
                timeout=ClientTimeout(total=120),  # Longer timeout
                headers={
                    **headers,
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                }
            ) as session:
                # First make a GET request to get any necessary tokens
                async with session.get(url) as response:
                    if response.status != 200:
                        return None
                    
                    # Extract any CSRF tokens if present
                    html = await response.text()
                    csrf_token = self._extract_csrf_token(html)
                    
                    if csrf_token:
                        headers['X-CSRF-Token'] = csrf_token

                # Make the actual POST request
                async with session.post(
                    url,
                    data=payload,
                    headers=headers,
                    allow_redirects=True
                ) as response:
                    if response.status == 200:
                        return await response.text()

        except Exception as e:
            logger.error(f"Fallback request failed: {str(e)}")
            return None

    @staticmethod
    def _extract_csrf_token(html: str) -> Optional[str]:
        """Extract CSRF token from HTML content"""
        import re
        
        # Common patterns for CSRF tokens
        patterns = [
            r'<meta name="csrf-token" content="([^"]+)"',
            r'<input[^>]+name="authenticity_token"[^>]+value="([^"]+)"',
            r'csrf_token["\s:]+"([^"]+)"'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                return match.group(1)
        
        return None
