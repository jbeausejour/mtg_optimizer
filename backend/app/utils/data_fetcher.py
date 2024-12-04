import asyncio
import logging
import datetime
import re
import socket
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

import aiohttp
import pandas as pd
from bs4 import BeautifulSoup
import dns.resolver
from tenacity import retry, stop_after_attempt, wait_exponential
from aiohttp import ClientTimeout

from app.extensions import db
from app.dto.optimization_dto import QUALITY_MAPPING, LANGUAGE_MAPPING
from app.models.card import UserBuylistCard
from app.models.scan import Scan, ScanResult
from app.models.site import Site
from app.utils.helpers import (
    clean_card_name,
    extract_numbers,
    normalize_price,
    parse_card_string,
)

logger = logging.getLogger(__name__)

from threading import Lock

class ErrorCollector:
    _instance = None
    _lock = Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance.unknown_languages = set()
                cls._instance.unknown_qualities = set()
                cls._instance.unreachable_stores = set()
            return cls._instance
    
    def reset(self):
        """Reset all error collections"""
        with self._lock:
            self.unknown_languages.clear()
            self.unknown_qualities.clear()
            self.unreachable_stores.clear()
    
    @classmethod
    def get_instance(cls):
        return cls()

class ExternalDataSynchronizer:

    STRATEGY_ADD_TO_CART = 1
    STRATEGY_SCRAPPER = 2
    STRATEGY_HAWK = 3

    def __init__(self):
        self.session = None
        self.timeout = ClientTimeout(total=30)  # 30 seconds timeout
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36",
        }
        self.max_retries = 3
        self.errors = {
            'unknown_languages': set(),
            'unknown_qualities': set()
        }
        self.error_collector = ErrorCollector.get_instance()
        self.error_collector.reset()  # Reset for new scraping session

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(headers=self.headers)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.session.close()

    async def resolve_dns(self, hostname):
        """Enhanced DNS resolution with multiple fallback options"""
        try:
            # Try system resolver first
            loop = asyncio.get_event_loop()
            addresses = await loop.run_in_executor(None, socket.gethostbyname_ex, hostname)
            if addresses and addresses[2]:
                logger.info(f"Successfully resolved {hostname} to {addresses[2][0]}")
                return addresses[2][0]
            
            # Fallback to manual resolution
            info = await asyncio.get_event_loop().getaddrinfo(
                hostname, None, 
                family=socket.AF_INET,
                proto=socket.IPPROTO_TCP,
            )
            if info and info[0] and info[0][4]:
                logger.info(f"Fallback resolution successful for {hostname}: {info[0][4][0]}")
                return info[0][4][0]
                
        except socket.gaierror as e:
            logger.warning(f"DNS resolution failed for {hostname}: {e}")
            # Try to use a public DNS server as last resort
            try:
                resolver = dns.resolver.Resolver()
                resolver.nameservers = ['8.8.8.8', '1.1.1.1']  # Google DNS, Cloudflare DNS
                answers = resolver.resolve(hostname, 'A')
                if answers:
                    logger.info(f"Public DNS resolution successful for {hostname}")
                    return answers[0].address
            except Exception as e:
                logger.error(f"All DNS resolution methods failed for {hostname}: {e}")
        return None

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def fetch_url(self, url):
        """Enhanced URL fetching with better error handling"""
        try:
            parsed_url = urlparse(url)
            hostname = parsed_url.hostname

            ip = await self.resolve_dns(hostname)
            if not ip:
                logger.error(f"DNS resolution failed completely for {hostname}")
                return None

            # Create custom connector with resolved IP
            connector = aiohttp.TCPConnector(
                ssl=False,
                force_close=True,
                ttl_dns_cache=300,
            )

            try:
                async with aiohttp.ClientSession(connector=connector) as session:
                    headers = {
                        **self.headers,
                        'Host': hostname  # Important: set original hostname
                    }
                    
                    async with session.get(
                        url,
                        timeout=self.timeout,
                        headers=headers,
                        allow_redirects=True
                    ) as response:
                        if response.status >= 400:
                            logger.warning(f"HTTP {response.status} from {url}")
                            return None
                        return await response.text()
            except Exception as e:
                logger.error(f"Request failed for {url}: {str(e)}")
                return None

        except Exception as e:
            logger.error(f"Fatal error fetching {url}: {str(e)}")
            return None

    async def post_request(self, url, payload):
        try:
            async with self.session.post(url, data=payload) as response:
                return await response.text()
        except Exception as e:
            logger.error(f"Error posting to {url}: {str(e)}")
            return None

    async def get_auth_token(self, soup, site):
        """Enhanced token fetching with more fallbacks"""
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

        # Method 4: Script based (some sites store token in JS)
        scripts = soup.find_all("script")
        for script in scripts:
            if script.string and any(x in script.string for x in ['csrf', 'token', 'auth']):
                import re
                token_match = re.search(r'["\']csrf[_-]token["\']\s*:\s*["\']([^"\']+)["\']', script.string)
                if token_match:
                    token = token_match.group(1)
                    logger.debug(f"Found auth token via script for {site.name}")
                    return token

        # Add new fallback methods
        if not token:
            # Try JavaScript variable parsing
            scripts = soup.find_all("script")
            for script in scripts:
                if script.string:
                    # Look for common token patterns
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

        # If still no token, try to proceed without one
        if not token:
            logger.warning(f"No auth token found for {site.name}, will try to proceed without it")
            return ""  # Return empty string instead of None
            
        return token

    async def scrape_multiple_sites(self, sites, card_names, strategy='nsga-ii', scan_id=None):
        """
        Scrape multiple sites for card data
        Args:
            sites: List of Site objects to scrape
            card_names: List of card names to search for
            strategy: Optimization strategy to use
            scan_id: Optional ID of the current scan
        """
        results = []
        logger.info(f"Starting scrape for {len(sites)} sites, {len(card_names)} cards")
        
        async with aiohttp.ClientSession(headers=self.headers, timeout=self.timeout) as session:
            self.session = session
            try:
                tasks = []
                for site in sites:
                    logger.info(f"Creating scraping task for site: {site.name}")
                    task = asyncio.create_task(self.process_site(site, card_names, strategy))
                    tasks.append(task)
                
                # Process tasks in batches
                BATCH_SIZE = 5
                total_batches = (len(tasks) + BATCH_SIZE - 1) // BATCH_SIZE
                
                for batch_num, i in enumerate(range(0, len(tasks), BATCH_SIZE), 1):
                    logger.info(f"Processing batch {batch_num}/{total_batches}")
                    batch = tasks[i:i + BATCH_SIZE]
                    batch_results = await asyncio.gather(*batch, return_exceptions=True)
                    
                    for result in batch_results:
                        if isinstance(result, Exception):
                            logger.error(f"Batch processing error: {str(result)}")
                        elif result:
                            logger.info(f"Successfully processed batch result with {len(result)} items")
                            results.extend(result)
                
                logger.info(f"Completed scraping with {len(results)} total results")
                return results
                
            except Exception as e:
                logger.error(f"Fatal error in scrape_multiple_sites: {str(e)}")
                raise

    async def search_crystalcommerce(self, site, card_names):
        search_url = site.url
        try:
            response_text = await self.fetch_url(search_url)
            if not response_text:
                logger.warning(f"No response from {site.name}")
                return None

            soup = BeautifulSoup(response_text, "html.parser")
            
            # Try to get auth token using multiple methods
            auth_token = await self.get_auth_token(soup, site)
            
            if not auth_token:
                # Try direct search without token
                direct_url = f"{search_url}?q={'+'.join(card_names)}"
                logger.info(f"Attempting direct search for {site.name}")
                response_text = await self.fetch_url(direct_url)
                if response_text:
                    return BeautifulSoup(response_text, "html.parser")
                return None

            # Continue with normal flow using auth token
            cards_payload = "\r\n".join(card_names)
            payload = {
                "authenticity_token": auth_token,
                "query": cards_payload,
                "submit": "Continue",
            }

            response_text = await self.post_request(search_url, payload)
            if not response_text:
                logger.warning(f"No response from post request to {site.name}")
                return None
                
            return BeautifulSoup(response_text, "html.parser")
            
        except Exception as e:
            logger.error(f"Error searching {site.name}: {str(e)}")
            return None

    async def process_site(self, site, card_names, strategy):
        """Process a single site and return results without saving to DB"""
        logger.info(f"Processing site {site.name} for {len(card_names)} cards using strategy {strategy}")
        try:
            soup = await self.search_crystalcommerce(site, card_names)
            if not soup:
                self.error_collector.unreachable_stores.add(site.name)
                logger.warning(f"No data received from {site.name}")
                return None

            cards_df = self.extract_info(soup, site, card_names, strategy)
            if cards_df is not None and not cards_df.empty:
                # Create summary of results
                summary = cards_df.groupby(['set_name', 'foil']).agg({
                    'name': 'count',
                    'price': ['min', 'max', 'mean'],
                    'quantity': 'sum'
                }).round(2)
                
                logger.info(f"Successfully extracted {len(cards_df)} cards from {site.name}")
                for (set_name, foil), row in summary.iterrows():
                    logger.info(f"{site.name}:  {set_name} ({'Foil' if foil else 'Regular'}): "
                              f"{int(row[('name', 'count')])} cards, "
                              f"Price range: ${row[('price', 'min')]} - ${row[('price', 'max')]}, "
                              f"Avg: ${row[('price', 'mean')]}, "
                              f"Total qty: {int(row[('quantity', 'sum')])}")

                # Convert DataFrame rows to results
                results = []
                for _, row in cards_df.iterrows():
                    result = {
                        'site_id': site.id,
                        'name': row['name'],
                        'set_name': row['set_name'],
                        'price': float(row.get('price', 0.0)),
                        'version': row.get('version', 'Standard'),
                        'foil': bool(row.get('foil', False)),
                        'quality': row['quality'],
                        'language': row['language'],
                        'quantity': int(row.get('quantity', 0))
                    }
                    results.append(result)

                return results
            else:
                logger.warning(f"No valid cards found for {site.name}")
                return None
                
        except Exception as e:
            logger.error(f"Error processing site {site.name}: {str(e)}")
            return None

    @staticmethod
    def convert_foil_to_bool(foil_value):
        """Convert foil value to boolean"""
        if isinstance(foil_value, bool):
            return foil_value
        if isinstance(foil_value, str):
            return foil_value.lower() in ['foil', 'true', '1', 'yes']
        return False

    @staticmethod
    def normalize_quality(quality):
        """Normalize quality to standard values"""
        logger.debug(f"=== Starting quality normalization for: {quality} ===")
        
        if not quality:
            logger.debug("Empty quality value, defaulting to NM")
            return 'NM'
            
        try:
            # Strip whitespace and convert to uppercase for consistent comparison
            quality_str = str(quality).strip().upper()
            
            # Create uppercase version of mapping for case-insensitive comparison
            upper_mapping = {k.upper(): v for k, v in QUALITY_MAPPING.items()}
            
            # Try to find direct match in uppercase mapping
            if quality_str in upper_mapping:
                normalized = upper_mapping[quality_str]
                logger.debug(f"Found quality mapping: '{quality}' -> '{normalized}'")
                return normalized
                
            # Handle special case for "MINT/NEAR-MINT" -> "NM"
            if any(x in quality_str for x in ['MINT', 'NEAR-MINT', 'NM']):
                logger.debug(f"Found mint-related quality: '{quality}', mapping to NM")
                return 'NM'
                
            # If no match found, log warning and return NM (being optimistic here)
            ErrorCollector.get_instance().unknown_qualities.add(quality)
            logger.warning(f"Unknown quality value: '{quality}'")
            return 'NM'
                
        except Exception as e:
            logger.error(f"Error normalizing quality '{quality}': {str(e)}")
            return 'NM'

    @classmethod
    async def update_all_cards(cls):
        card_query = (
            UserBuylistCard.query.with_entities(
                UserBuylistCard.name).distinct().all()
        )
        card_names = [card.name for card in card_query]
        sites = Site.query.filter_by(active=True).all()

        async with cls() as fetcher:
            tasks = [fetcher.process_site(site, card_names) for site in sites]
            await asyncio.gather(*tasks)

    @staticmethod
    def extract_info(soup, site, card_names, strategy):
        """
        Extract card info from the provided HTML soup using the given strategy.
        """
        if soup is None:
            logger.warning(f"Soup is None for site {site.name}")
            return pd.DataFrame()

        cards = []
        seen_variants = set()

        excluded_categories = {
            "playmats",
            "booster packs",
            "booster box",
            "mtg booster boxes",
            "art series",
            "fat packs and bundles",
            "mtg booster packs",
            "magic commander deck",
            "world championship deck singles",
            "The Crimson Moon's Fairy Tale",
            "rpg accessories",
            "scan other",
            "intro packs and planeswalker decks",
            "wall scrolls",
        }

        if strategy == ExternalDataSynchronizer.STRATEGY_HAWK:
            return pd.DataFrame(
                [
                    card.to_dict()
                    for card in ExternalDataSynchronizer.strategy_hawk(soup)
                ]
            )

        content = soup.find(
            "div", {"class": ["content", "content clearfix",
                              "content inner clearfix"]}
        )
        if content is None:
            logger.error(f"Content div not found for site {site.name}")
            return pd.DataFrame()

        products_containers = content.find_all(
            "div", {"class": "products-container browse"}
        )
        if not products_containers:
            logger.warning(f"No products container found for site {site.name}")
            return pd.DataFrame()

        required_fields = {
            'name',
            'set_name',
            'quality',
            'language',
            'quantity',
            'price',
            'version',
            'foil'
        }

        logger.info(f"Processing container for {site.name}")
        for container in products_containers:
            #logger.info(f"Found products container in {site.name}")
            logger.debug(f"Container HTML: {container.prettify()}")
            
            items = container.find_all("li", {"class": "product"})
            logger.debug(f"Found {len(items)} product items in {site.name}")
            
            for item in items:
                try:
                    logger.debug(f"Processing item in {site.name}: {item.get('id', 'no-id')}")
                    card_attrs = ExternalDataSynchronizer.process_product_item(
                        item, site, card_names, excluded_categories
                    )
                    if card_attrs:
                        logger.debug(f"Valid card found in {site.name}: {card_attrs['name']}") 
                        if all(key in card_attrs for key in required_fields):
                            ExternalDataSynchronizer.process_variants(
                                item, card_attrs, cards, seen_variants, strategy
                            )
                        else:
                            missing = required_fields - set(card_attrs.keys())
                            logger.warning(f"Missing fields {missing} for card in {site.name}")
                    else:
                        logger.debug(f"Invalid card item in {site.name}")
                except Exception as e:
                    logger.exception(f"Error processing item in {site.name}")
                    continue

        if not cards:
            logger.warning(f"No valid cards found in container for {site.name}")
            return pd.DataFrame()

        try:
            df = pd.DataFrame(cards)
            # Ensure standard column names and data types
            standard_columns = {
                'name': str,
                'set_name': str,
                'price': float,
                'version': str,
                'foil': bool,
                'quality': str,
                'language': str,
                'quantity': int
            }
            
            # Add missing columns with default values
            for col, dtype in standard_columns.items():
                if col not in df.columns:
                    df[col] = dtype()
                df[col].astype(dtype)
            
            # Normalize quality and language values
            df['quality'] = df['quality'].apply(ExternalDataSynchronizer.normalize_quality)
            df['language'] = df['language'].apply(ExternalDataSynchronizer.normalize_language)
            
            return df
            
        except Exception as e:
            logger.error(f"Error creating DataFrame for {site.name}: {str(e)}")
            return pd.DataFrame()

    @staticmethod
    def process_product_item(item, site, card_names, excluded_categories):
        """Fixed dict handling with better HTML inspection"""
        try:
            logger.debug(f"Starting process_product_item for {site.name}")
            
            if ExternalDataSynchronizer.is_yugioh_card(item):
                logger.debug(f"Skipping Yugioh card in {site.name}")
                return None

            # Debug HTML structure
            logger.debug(f"Product HTML in {site.name}: {item.prettify()}")

            meta = item.find("div", {"class": "meta"})
            if not meta:
                logger.warning(f"No meta div found for item in {site.name}")
                return None
            
            logger.debug(f"Meta div in {site.name}: {meta.prettify()}")
                
            category_span = meta.find("span", {"class": "category"})
            name_header = meta.find("h4", {"class": "name"})
            
            if not category_span or not name_header:
                logger.warning(f"Missing category or name header in {site.name}")
                logger.debug(f"Category span: {category_span}")
                logger.debug(f"Name header: {name_header}")
                return None
                
            test_category = category_span.text.strip()
            test_title = name_header.text.strip()
            
            logger.debug(f"Found card: '{test_title}' in category: '{test_category}' for {site.name}")

            if any(cat in test_category.lower() for cat in excluded_categories):
                logger.debug(f"Category {test_category} is in excluded list for {site.name}")
                return None

            # Create a dictionary with standardized keys (all lowercase)
            card_info = {
                'name': '',
                'set_name': test_category,
                'foil': False,
                'quality': 'Near Mint',
                'language': 'English',
                'quantity': 0,
                'price': 0.0,
                'version': 'Standard'
            }

            parsed_card = parse_card_string(test_title)
            logger.debug(f"Parsed card result for {site.name}: {parsed_card}")
            
            if isinstance(parsed_card, dict):
                # Update key mapping to handle both old and new formats
                key_mapping = {
                    'Name': 'name',
                    'Foil': 'foil',
                    'Edition': 'set_name',
                    'Quality': 'quality',
                    'Language': 'language',
                    'Quantity': 'quantity',
                    'Price': 'price',
                    'Version': 'version'
                }
                
                for old_key, new_key in key_mapping.items():
                    if old_key in parsed_card:
                        card_info[new_key] = parsed_card[old_key]
            else:
                logger.debug(f"Parsed card is object with name: {getattr(parsed_card, 'name', None)}")
                # Handle object-style parsing result
                card_info['name'] = getattr(parsed_card, 'name', test_title)
                card_info['foil'] = getattr(parsed_card, 'foil', False)

            # Clean and validate card name
            original_name = card_info['name']  
            card_info['name'] = clean_card_name(card_info['name'], card_names)  
            logger.debug(f"Card name cleaned from '{original_name}' to '{card_info['name']}' for {site.name}")

            if not card_info['name']: 
                logger.warning(f"Card name cleaned to empty string in {site.name}")
                return None
                
            if (card_info['name'] not in card_names and  
                card_info['name'].split(" // ")[0].strip() not in card_names):
                logger.debug(f"Card '{card_info['name']}' not in requested list for {site.name}")
                logger.debug(f"Available card names: {card_names}")
                return None

            logger.debug(f"Successfully processed card '{card_info['name']}' for {site.name}")  
            return card_info

        except Exception as e:
            logger.exception(f"Error in process_product_item for {site.name}")
            logger.error(f"Full error: {str(e)}")
            logger.error(f"Item HTML: {item.prettify() if item else 'None'}")
            return None

    @staticmethod
    def process_variants(item, card, cards, seen_variants, strategy):
        variants = item.find("div", {"class": "variants"})
        for variant in variants.find_all("div", {"class": "variant-row"}):
            card_variant = (
                ExternalDataSynchronizer.strategy_add_to_cart(card, variant)
                if strategy == ExternalDataSynchronizer.STRATEGY_ADD_TO_CART
                else ExternalDataSynchronizer.strategy_scrapper(card, variant)
            )
            if card_variant is not None:
                # Create a hashable key from the variant's relevant data
                variant_key = (
                    card_variant.get('name', ''),          # Updated keys
                    card_variant.get('set_name', ''),      # to match
                    card_variant.get('quality', ''),       # new schema
                    card_variant.get('language', ''),
                    card_variant.get('foil', False),
                    card_variant.get('version', 'Standard')
                )
                if variant_key not in seen_variants:
                    cards.append(card_variant)
                    seen_variants.add(variant_key)

    @staticmethod
    def is_yugioh_card(item):
        image = item.find("div", {"class": "image"})
        a_tag = image and image.find("a", href=True)
        return a_tag and "yugioh" in a_tag["href"]

    @staticmethod
    def normalize_language(language):
        """Normalize language to standard values"""

        if not language:
            logger.info("Empty language value, defaulting to English")
            return 'English'

        
            
        cleaned_language = language.lower().strip()
        normalized = LANGUAGE_MAPPING.get(cleaned_language, 'Unknown')
        
        if normalized == 'Unknown' and cleaned_language not in LANGUAGE_MAPPING:
            ErrorCollector.get_instance().unknown_languages.add(language)
            logger.warning(f"Unknown language value: '{language}' (cleaned: '{cleaned_language}')")
        # else:
        #     logger.info(f"Normalized language from '{language}' to '{normalized}'")
            
        return normalized

    @staticmethod
    def strategy_add_to_cart(card, variant):
        """Modified to handle both dict and object card data"""
        if "no-stock" in variant.get("class", []) or "0 In Stock" in variant:
            return None

        form_element = variant.find("form", {"class": "add-to-cart-form"})
        if not form_element:
            return None

        attributes = form_element.attrs
        if "data-name" not in attributes:
            return None

        unclean_name, product_version, product_foil = (
            ExternalDataSynchronizer.find_name_version_foil(
                attributes["data-name"])
        )

        # Create new card dict if input is dict, otherwise modify object
        if isinstance(card, dict):
            card_data = card.copy()  # Create copy to avoid modifying original
            quality_language = ExternalDataSynchronizer.normalize_variant_description(
                attributes["data-variant"]
            )
            quality, language = quality_language[:2]
            quality = ExternalDataSynchronizer.normalize_quality(quality)  # Normalize quality here
            language = ExternalDataSynchronizer.normalize_language(language)  # Add this line

            select_tag = variant.find("select", {"class": "qty"}) or variant.find(
                "input", {"class": "qty"}
            )
            qty_available = (
                select_tag["max"] if select_tag and "max" in select_tag.attrs else "0"
            )

            card_data.update({
                'quality': quality, 
                'language': language,
                'quantity': int(qty_available),  
                'set_name': attributes["data-category"], 
                'price': normalize_price(attributes["data-price"]),  
                'foil': ExternalDataSynchronizer.convert_foil_to_bool(product_foil)  # Convert foil value here
            })
            return card_data
        else:
            # Handle object-style card
            card.foil = ExternalDataSynchronizer.convert_foil_to_bool(product_foil)
            if product_version:
                card.set_name = product_version

            quality_language = ExternalDataSynchronizer.normalize_variant_description(
                attributes["data-variant"]
            )
            quality, language = quality_language[:2]
            quality = ExternalDataSynchronizer.normalize_quality(quality)  # Normalize quality here
            language = ExternalDataSynchronizer.normalize_language(language)  # Add this line

            select_tag = variant.find("select", {"class": "qty"}) or variant.find(
                "input", {"class": "qty"}
            )
            qty_available = (
                select_tag["max"] if select_tag and "max" in select_tag.attrs else "0"
            )

            card.quality = quality
            card.language = language
            card.quantity = int(qty_available)
            card.set_name = attributes["data-category"]
            card.price = normalize_price(attributes["data-price"])
            
            return card

    @staticmethod
    def strategy_scrapper(card, variant):
        """Modified to add error context"""
        if "no-stock" in variant.get("class", []) or "0 In Stock" in variant:
            return None

        try:
            quality, language = ExternalDataSynchronizer.extract_quality_language(
                card, variant
            )
            if quality is None or language is None:
                return None
                
            quality = ExternalDataSynchronizer.normalize_quality(quality)  # Normalize quality here
            language = ExternalDataSynchronizer.normalize_language(language)  # Add this line

            quantity = ExternalDataSynchronizer.extract_quantity(card, variant)
            if quantity is None:
                return None

            price = ExternalDataSynchronizer.extract_price(card, variant)

            # Create new card dict if input is dict, otherwise modify object
            if isinstance(card, dict):
                card_data = card.copy()
                card_data.update({
                    'quality': quality,      # Changed from 'Quality'
                    'language': language,    # Changed from 'Language'
                    'quantity': quantity,    # Changed from 'Quantity'
                    'price': price          # Changed from 'Price'
                })
                logger.debug(f"Updated card data: {card_data}")
                return card_data
            else:
                # Handle object-style card
                card.quality = quality
                card.language = language
                card.quantity = quantity
                card.price = price
                return card

        except Exception as e:
            card_name = card.get('name', '') if isinstance(card, dict) else getattr(card, 'name', '')  
            logger.exception(f"Error in strategy_scrapper for {card_name}: {str(e)}")
            return None

    @staticmethod
    def strategy_hawk(soup):
        cards_data = []
        for card_div in soup.select(".hawk-results__item"):
            card_details = {
                "name": card_div.select_one(
                    ".hawk-results__hawk-contentTitle"
                ).get_text(strip=True),
                "image_url": card_div.select_one(".hawk-results__item-image img")[
                    "src"
                ],
                "edition": card_div.select_one(
                    ".hawk-results__hawk-contentSubtitle"
                ).get_text(strip=True),
                "variants": [],
                "stock": [],
                "prices": [],
            }

            for variant_div in card_div.select(
                '.hawk-results__hawk-contentVariants input[type="radio"]'
            ):
                variant_details = {
                    "variant_id": variant_div["id"],
                    "condition": (
                        variant_div.get(
                            "data-options", "").split(",")[0].split("|")[1]
                        if "condition" in variant_div.get("data-options", "")
                        else ""
                    ),
                    "finish": (
                        variant_div.get(
                            "data-options", "").split(",")[1].split("|")[1]
                        if "finish" in variant_div.get("data-options", "")
                        else ""
                    ),
                }
                card_details["variants"].append(variant_details)

            for stock_span in card_div.select(".hawkStock"):
                card_details["stock"].append(
                    {
                        "variant_id": stock_span["data-var-id"],
                        "in_stock": stock_span.get_text(strip=True),
                    }
                )
            for price_span in card_div.select(".hawkPrice"):
                card_details["prices"].append(
                    {
                        "variant_id": price_span["data-var-id"],
                        "price": price_span.get_text(strip=True),
                    }
                )

            cards_data.append(card_details)

        return cards_data

    @staticmethod
    def find_name_version_foil(place_holder):
        items = re.split(r" - ", place_holder)
        items = [x.strip() for x in items]
        product_name = items[0]
        product_version = ""
        product_foil = ""

        for item in items[1:]:
            if "Foil" in item:
                product_foil = item
            else:
                product_version = item

        return product_name, product_version, product_foil

    @staticmethod
    def normalize_variant_description(variant_description):
        cleaned_description = variant_description.split(":")[-1].strip()
        variant_parts = cleaned_description.split(",")
        return [part.strip() for part in variant_parts]

    @staticmethod
    def extract_quality_language(card, variant):
        """Extract and normalize quality and language from variant"""
        card_name = card.get('name', '') if isinstance(card, dict) else getattr(card, 'name', '')
        logger.debug(f"=== Extracting quality/language for card: {card_name} ===")
        
        variant_description = variant.find(
            "span", {"class": "variant-short-info variant-description"}
        ) or variant.find("span", {"class": "variant-short-info"})
        
        if variant_description:
            quality_language = ExternalDataSynchronizer.normalize_variant_description(
                variant_description.text
            )
            logger.debug(f"Raw quality_language parts: {quality_language}")
            
            if len(quality_language) >= 2:
                raw_quality, raw_language = quality_language[:2]
                logger.debug(f"Before normalization - Quality: {raw_quality}, Language: {raw_language}")
                
                # Normalize both values
                quality = ExternalDataSynchronizer.normalize_quality(raw_quality)
                language = ExternalDataSynchronizer.normalize_language(raw_language)
                
                logger.debug(f"After normalization - Quality: {quality}, Language: {language}")
                return quality, language
            else:
                logger.warning(f"Incomplete variant description: {variant_description.text}")
                logger.debug("Using default values: 'NM', 'English'")
                return 'NM', 'English'
        else:
            logger.error(f"No variant description found for card: {card_name}")
            return None, None

    @staticmethod
    def extract_quantity(card, variant):
        """Modified to handle both dict and object card data"""
        variant_qty = variant.find(
            "span", {"class": "variant-short-info variant-qty"}
        ) or variant.find("span", {"class": "variant-short-info"})
        if variant_qty:
            variant_qty = variant_qty.text.strip()
            return extract_numbers(variant_qty)
        else:
            card_name = card.get('name', '') if isinstance(card, dict) else getattr(card, 'name', '') 
            logger.error(
                f"Error in extract_quantity for {card_name}: variant-qty not found"
            )
            return None

    @staticmethod
    def extract_price(card, variant):
        """Modified to handle both dict and object card data"""
        price_elem = variant.find("span", {"class": "regular price"})
        if price_elem is not None:
            price_text = price_elem.text
            return normalize_price(price_text)
        else:
            card_name = card.get('name', '') if isinstance(card, dict) else getattr(card, 'name', '')  
            logger.error(
                f"Error in extract_price for {card_name}: Price element not found"
            )
            return 0.0