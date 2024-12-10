import logging
import os
import socket
import asyncio
from typing import Dict, Optional
import aiohttp
import dns.resolver
from aiohttp import ClientTimeout, TCPConnector
from urllib.parse import urlparse
from webdriver_manager.chrome import ChromeDriverManager
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium_stealth import stealth
import re

homedir = os.path.expanduser("~")
CHROME_DRIVER_PATH = f"{homedir}/Downloads/chromedriver-win64/chromedriver.exe"

logger = logging.getLogger(__name__)

class NetworkDriver:
    """Enhanced base class for network operations with connection pooling"""
    def __init__(self, max_connections: int = 100, keepalive_timeout: int = 30):
        self.timeout = ClientTimeout(total=30, connect=10, sock_read=20)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
        }
        self._session: Optional[aiohttp.ClientSession] = None
        self._connector = TCPConnector(
            limit=max_connections,
            ttl_dns_cache=300,
            keepalive_timeout=keepalive_timeout,
            force_close=False,
            enable_cleanup_closed=True
        )
        self._rate_limiters: Dict[str, asyncio.Semaphore] = {}
        self._default_rate_limit = asyncio.Semaphore(10)  # Default concurrent requests per domain

    async def __aenter__(self):
        if not self._session:
            self._session = aiohttp.ClientSession(
                connector=self._connector,
                headers=self.headers,
                timeout=self.timeout,
                trust_env=True
            )
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._session:
            await self._session.close()
            self._session = None

    def _get_rate_limiter(self, domain: str) -> asyncio.Semaphore:
        """Get or create rate limiter for a domain"""
        if domain not in self._rate_limiters:
            # Customize rate limits per domain if needed
            if 'example.com' in domain:
                self._rate_limiters[domain] = asyncio.Semaphore(5)  # Stricter limit
            else:
                self._rate_limiters[domain] = self._default_rate_limit
        return self._rate_limiters[domain]

    async def fetch_url(self, url, attempt=1, max_attempts=3):
        """Enhanced URL fetching with proper timeout handling"""
        try:
            parsed_url = urlparse(url)
            hostname = parsed_url.hostname
            ip = await self.resolve_dns(hostname)
            
            connector = aiohttp.TCPConnector(
                ssl=False,
                force_close=True,
                ttl_dns_cache=300,
            )

            timeout = aiohttp.ClientTimeout(total=30, connect=10, sock_connect=10, sock_read=10)

            async with aiohttp.ClientSession(
                connector=connector,
                timeout=timeout
            ) as session:
                headers = {
                    **self.headers,
                    'Host': hostname
                }
                
                async with session.get(
                    url,
                    headers=headers,
                    allow_redirects=True
                ) as response:
                    if response.status >= 400:
                        return None
                    return await response.text()

        except asyncio.TimeoutError:
            if attempt < max_attempts:
                logger.warning(f"Timeout fetching {url} (attempt {attempt}/{max_attempts})")
                return await self.fetch_url(url, attempt + 1, max_attempts)
            else:
                logger.error(f"Failed to fetch {url} after {max_attempts} attempts")
                return None
        except Exception as e:
            logger.error(f"Error fetching {url} (attempt {attempt}/{max_attempts}): {str(e)}")
            if attempt < max_attempts:
                return await self.fetch_url(url, attempt + 1, max_attempts)
            return None

    async def post_request(self, url, payload, attempt=1, max_attempts=3):
        """Enhanced POST request handling with proper timeout"""
        try:
            parsed_url = urlparse(url)
            hostname = parsed_url.hostname
            ip = await self.resolve_dns(hostname)
            
            timeout = aiohttp.ClientTimeout(total=45, connect=10, sock_connect=10, sock_read=30)
            headers = {
                **self.headers,
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Host': hostname
            }
            
            connector = aiohttp.TCPConnector(
                ssl=False,
                force_close=True,
                ttl_dns_cache=300,
            )
            
            async with aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers=headers
            ) as session:
                async with session.post(url, data=payload) as response:
                    if response.status == 200:
                        return await response.text()
                    return None
                        
        except asyncio.TimeoutError:
            if attempt < max_attempts:
                logger.warning(f"Timeout posting to {url} (attempt {attempt}/{max_attempts})")
                return await self.post_request(url, payload, attempt + 1, max_attempts)
            else:
                logger.error(f"Failed to post to {url} after {max_attempts} attempts")
                return None
        except Exception as e:
            logger.error(f"Error posting to {url} (attempt {attempt}/{max_attempts}): {str(e)}")
            if attempt < max_attempts:
                return await self.post_request(url, payload, attempt + 1, max_attempts)
            return None
    
    async def resolve_dns(self, hostname):
        """Enhanced DNS resolution with multiple fallback options"""
        try:
            # Try system resolver first
            loop = asyncio.get_event_loop()
            addresses = await loop.run_in_executor(None, socket.gethostbyname_ex, hostname)
            if addresses and addresses[2]:
                logger.info(f"\t o Successfully resolved {hostname} to {addresses[2][0]}")
                return addresses[2][0]
            
            # Fallback to manual resolution
            info = await asyncio.get_event_loop().getaddrinfo(
                hostname, None, 
                family=socket.AF_INET,
                proto=socket.IPPROTO_TCP,
            )
            if info and info[0] and info[0][4]:
                return info[0][4][0]
                
        except socket.gaierror:
            # Try to use public DNS servers as last resort
            try:
                resolver = dns.resolver.Resolver()
                resolver.nameservers = ['8.8.8.8', '1.1.1.1']
                answers = resolver.resolve(hostname, 'A')
                if answers:
                    return answers[0].address
            except Exception as e:
                logger.error(f"All DNS resolution methods failed for {hostname}: {e}")
        return None

    async def get_auth_token(self, soup, site):
        """Enhanced token fetching with multiple fallbacks"""
        token = None
        
        # Method 1: Standard auth token input
        auth_input = soup.find("input", {"name": ["authenticity_token", "csrf_token", "_token"]})
        if auth_input:
            token = auth_input.get("value")
            if token:
                logger.debug(f"Found auth token via input field for {site.name}")
                return token

        # Method 2: Meta tag
        meta_token = soup.find("meta", {"name": ["csrf-token", "csrf-param"]})
        if meta_token:
            token = meta_token.get("content")
            if token:
                logger.debug(f"Found auth token via meta tag for {site.name}")
                return token

        # Method 3: Form based
        form = soup.find("form", {"class": ["search-form", "advanced-search", "bulk-search"]})
        if form:
            hidden_input = form.find("input", {"type": "hidden", "name": ["authenticity_token", "csrf_token", "_token"]})
            if hidden_input:
                token = hidden_input.get("value")
                if token:
                    logger.debug(f"Found auth token via form for {site.name}")
                    return token

        # Method 4: Script based
        scripts = soup.find_all("script")
        for script in scripts:
            if script.string and any(x in script.string for x in ['csrf', 'token', 'auth']):
                token_match = re.search(r'["\']csrf[_-]token["\']\s*:\s*["\']([^"\']+)["\']', script.string)
                if token_match:
                    token = token_match.group(1)
                    logger.debug(f"Found auth token via script for {site.name}")
                    return token

        # Add new fallback methods - JavaScript variable parsing
        if not token:
            scripts = soup.find_all("script")
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
                            token = match.group(1)
                            logger.info(f"Found token via JS pattern for {site.name}")
                            return token

        logger.warning(f"No auth token found for {site.name}, will try to proceed without it")
        return ""

class SeleniumDriver(NetworkDriver):
    """Selenium driver with additional network capabilities"""
    def __init__(self):
        super().__init__()
        self.driver = None

    @staticmethod
    def get_driver(use_headless=True):
        """Initialize Chrome driver with automatic version management"""
        try:
            options = Options()
            if use_headless:
                options.add_argument("--headless")
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--log-level=3")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)

            # Use webdriver_manager to get correct ChromeDriver version
            driver_path = ChromeDriverManager().install()
            service = Service(driver_path)
            driver = webdriver.Chrome(service=service, options=options)

            stealth(
                driver,
                languages=["en-US", "en"],
                vendor="Google Inc.",
                platform="Win32",
                webgl_vendor="Intel Inc.",
                renderer="Intel Iris OpenGL Engine",
                fix_hairline=True,
            )

            logger.info("Successfully initialized Chrome driver with automated version management")
            return driver
        
        except Exception as e:
            logger.error(f"Failed to initialize Chrome driver: {str(e)}")
            return None
        
    def perform_get(self, url, wait_time=10):
        """Perform GET request using Selenium"""
        try:
            logger.info(f"Attempting Selenium GET for {url}")
            
            self.get(url)
            WebDriverWait(self, wait_time).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            return self.page_source
            
        except Exception as e:
            logger.error(f"Selenium GET failed for {url}: {str(e)}")
            return None

    def perform_post(self, url, payload, wait_time=10):
        """Perform POST request using Selenium"""
        try:
            logger.info(f"Attempting Selenium POST for {url}")
            
            # Create a form to submit
            script = """
                let form = document.createElement('form');
                form.method = 'POST';
                form.action = arguments[0];
            """
            
            # Add payload fields
            for key, value in payload.items():
                script += f"""
                    let input_{key} = document.createElement('input');
                    input_{key}.type = 'hidden';
                    input_{key}.name = '{key}';
                    input_{key}.value = '{value}';
                    form.appendChild(input_{key});
                """
                
            script += """
                document.body.appendChild(form);
                form.submit();
            """
            
            # Execute the form submission
            self.execute_script(script, url)
            
            # Wait for response
            WebDriverWait(self, wait_time).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            return self.page_source
            
        except Exception as e:
            logger.error(f"Selenium POST failed for {url}: {str(e)}")
            return None

    def quit(self):
        if self.driver:
            self.driver.quit()
            self.driver = None
