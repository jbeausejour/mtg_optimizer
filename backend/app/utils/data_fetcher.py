import asyncio
import logging
import re
from concurrent.futures import ThreadPoolExecutor
import json
from json import JSONDecodeError 
import pandas as pd
from bs4 import BeautifulSoup
from threading import Lock

from app.extensions import db
from app.constants import CardLanguage, CardQuality, CardVersion
from app.services import CardService
from app.utils.helpers import (
    clean_card_name,
    extract_numbers,
    normalize_price,
)
from app.utils.selenium_driver import NetworkDriver, SeleniumDriver

logger = logging.getLogger(__name__)

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
    STRATEGY_CRYSTAL = 1
    STRATEGY_SCRAPPER = 2
    STRATEGY_HAWK = 3
    STRATEGY_SHOPIFY = 4
    STRATEGY_OTHER = 5
    strats = {
        "crystal": STRATEGY_CRYSTAL,
        "scrapper": STRATEGY_SCRAPPER,
        "hawk": STRATEGY_HAWK,
        "shopify": STRATEGY_SHOPIFY,
        "other": STRATEGY_OTHER,
    }

    def __init__(self):
        self.network = NetworkDriver()
        self.selenium_driver = None
        self.use_selenium_fallback = True
        self.error_collector = ErrorCollector.get_instance()
        self.error_collector.reset()
        self._selenium_attempts = 0
        self.MAX_SELENIUM_ATTEMPTS = 3

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.cleanup_selenium()

    async def get_selenium_driver(self):
        """Lazily initialize selenium driver with retry logic"""
        if not self.selenium_driver:
            try:
                self.selenium_driver = SeleniumDriver.get_driver(use_headless=True)
                logger.info("Successfully initialized Selenium driver")
            except Exception as e:
                logger.error(f"Failed to initialize Selenium driver: {str(e)}")
                return None
        return self.selenium_driver

    async def cleanup_selenium(self):
        """Cleanup selenium driver with proper error handling"""
        if self.selenium_driver:
            try:
                self.selenium_driver.quit()
            except Exception as e:
                logger.error(f"Error cleaning up Selenium driver: {str(e)}")
            finally:
                self.selenium_driver = None
                self._selenium_attempts = 0

    async def search_crystalcommerce(self, site, card_names):
        """Enhanced search with proper fallback to Selenium"""
        search_url = site.url
        
        # First attempt with NetworkDriver
        try:
            response_text = await self.network.fetch_url(search_url)
            if response_text:
                soup = BeautifulSoup(response_text, "html.parser")
                auth_token = await self.network.get_auth_token(soup, site)
                
                if auth_token:
                    cards_payload = "\r\n".join(card_names)
                    payload = {
                        "authenticity_token": auth_token,
                        "query": cards_payload,
                        "submit": "Continue",
                    }
                    
                    response_text = await self.network.post_request(search_url, payload)
                    if response_text:
                        return BeautifulSoup(response_text, "html.parser")
        except Exception as e:
            logger.warning(f"NetworkDriver attempt failed for {site.name}: {str(e)}")

        # Fallback to Selenium if network request fails
        if self.use_selenium_fallback and self._selenium_attempts < self.MAX_SELENIUM_ATTEMPTS:
            try:
                logger.info(f"Attempting Selenium fallback for {site.name}")
                self._selenium_attempts += 1
                
                driver = await self.get_selenium_driver()
                if not driver:
                    return None
                    
                # Perform GET request
                response_text = driver.perform_get(search_url)
                if not response_text:
                    return None
                    
                soup = BeautifulSoup(response_text, "html.parser")
                auth_token = await self.network.get_auth_token(soup, site)
                
                if auth_token:
                    cards_payload = "\r\n".join(card_names)
                    payload = {
                        "authenticity_token": auth_token,
                        "query": cards_payload,
                        "submit": "Continue",
                    }
                    
                    response_text = driver.perform_post(search_url, payload)
                    if response_text:
                        return BeautifulSoup(response_text, "html.parser")
                        
                # Try direct search as last resort
                direct_url = f"{search_url}?q={'+'.join(card_names)}"
                response_text = driver.perform_get(direct_url)
                if response_text:
                    return BeautifulSoup(response_text, "html.parser")
                    
            except Exception as e:
                logger.error(f"Selenium fallback failed for {site.name}: {str(e)}")
            finally:
                if self._selenium_attempts >= self.MAX_SELENIUM_ATTEMPTS:
                    logger.warning(f"Max Selenium attempts reached for {site.name}")
                    self.use_selenium_fallback = False
                    
        self.error_collector.unreachable_stores.add(site.name)
        return None

    async def scrape_multiple_sites(self, sites, card_names):
        """Enhanced scraping with proper Selenium integration"""
        results = []
        logger.info(f"Starting scrape for {len(sites)} sites, {len(card_names)} cards")
        
        async with self.network as session:
            try:
                tasks = []
                for i, site in enumerate(sites, 1):
                    logger.info(f"Creating scraping task {i} for site: {site.name}")
                    task = asyncio.create_task(self.process_site(site, card_names))
                    tasks.append(task)
                
                # Process tasks in batches with proper cleanup
                BATCH_SIZE = 5
                total_batches = (len(tasks) + BATCH_SIZE - 1) // BATCH_SIZE
                
                for batch_num, i in enumerate(range(0, len(tasks), BATCH_SIZE), 1):
                    try:
                        logger.info(f"Processing batch {batch_num}/{total_batches}")
                        batch = tasks[i:i + BATCH_SIZE]
                        batch_results = await asyncio.gather(*batch, return_exceptions=True)
                        
                        for result in batch_results:
                            if isinstance(result, Exception):
                                logger.error(f"Batch processing error: {str(result)}")
                            elif result:
                                results.extend(result)
                                
                    except Exception as e:
                        logger.error(f"Error processing batch {batch_num}: {str(e)}")
                    finally:
                        # Reset Selenium attempts between batches
                        self._selenium_attempts = 0
                        
                logger.info(f"Completed scraping with {len(results)} total results")
                return results
                
            except Exception as e:
                logger.error(f"Fatal error in scrape_multiple_sites: {str(e)}")
                raise
            finally:
                await self.cleanup_selenium()

    async def detect_response_type(self, response_text):
        """Detect response type and format"""
        if not response_text:
            return None, None
            
        # Check if it's JSON (Shopify API response)
        try:
            json_data = json.loads(response_text)
            if isinstance(json_data, list) and json_data and 'searchName' in json_data[0]:
                return 'shopify_json', json_data
        except json.JSONDecodeError:
            pass
            
        # Check if it's HTML
        if any(marker in response_text for marker in ['<!DOCTYPE html>', '<html', '<?xml']):
            # Check for loading indicators
            loading_indicators = [
                "Searching... Please wait",
                "custom-loader",
                "savedLoader",
                "loading-overlay",
                "spinner"
            ]
            is_loading = any(indicator in response_text for indicator in loading_indicators)
            return 'html', {'is_loading': is_loading}
            
        return 'unknown', None

    @staticmethod
    def log_cards_df_stat(site, cards_df):
        summary = cards_df.groupby(['name', 'foil']).agg({
            'set_name': 'count',
            'price': ['min', 'max', 'mean'],
            'quantity': 'sum'
        }).round(2)
        
        logger.info(f"Results from {site.name} - {len(cards_df)} cards found:")
        logger.info("=" * 100)
        logger.info(f"{'Name':<40} {'Type':<8} {'Sets':>5} {'Min $':>8} {'Max $':>8} {'Avg $':>8} {'Qty':>5}")
        logger.info("-" * 100)
        
        for (name, foil), row in summary.iterrows():
            logger.info(
                f"{name[:38]:<40} "
                f"{'Foil' if foil else 'Regular':<8} "
                f"{int(row[('set name', 'count')]):>5} "
                f"{row[('price', 'min')]:>8.2f} "
                f"{row[('price', 'max')]:>8.2f} "
                f"{row[('price', 'mean')]:>8.2f} "
                f"{int(row[('quantity', 'sum')]):>5}"
            )
        logger.info("=" * 100 + "\n")

    @staticmethod
    def log_site_error(site_name, error_type, details=None):
        """Standardized error logging for site processing"""
        error_box_width = 80
        logger.error("=" * error_box_width)
        logger.error(f"Site Processing Error: {site_name}")
        logger.error("-" * error_box_width)
        logger.error(f"Error Type: {error_type}")
        if details:
            logger.error(f"Details: {details}")
        logger.error("=" * error_box_width + "\n")

    async def process_site(self, site, card_names):
        """Process a single site and return results without saving to DB"""
        strategy = ExternalDataSynchronizer.strats.get(site.method.lower(), 
                                    ExternalDataSynchronizer.STRATEGY_CRYSTAL)
        
        logger.info(f"Processing site: {site.name}")
        logger.info(f"\t o Strategy: {site.method}")
        logger.info(f"\t o URL: {site.url}")
        
        try:
            if strategy == ExternalDataSynchronizer.STRATEGY_SHOPIFY:
                # Get data from Shopify API
                json_data = await self.search_shopify(site, card_names)
                
                if not json_data:
                    self.error_collector.unreachable_stores.add(site.name)
                    self.log_site_error(site.name, "Connection Error", 
                                    "Failed to retrieve data from Shopify API.")
                    return None
                    
                cards_df = self.extract_info_shopify_json(json_data, site, card_names)
                
            elif strategy == ExternalDataSynchronizer.STRATEGY_HAWK:
                
                json_data = await self.search_hawk(site, card_names)
            
                if not json_data:
                    self.error_collector.unreachable_stores.add(site.name)
                    self.log_site_error(site.name, "Connection Error", 
                                    "Failed to retrieve data from Hawk API.")
                    return None
                    
                cards_df = self.extract_info_hawk_json(json_data, site, card_names)
                
            else:
                soup = await self.search_crystalcommerce_simple(site, card_names)
                if not soup:
                    self.error_collector.unreachable_stores.add(site.name)
                    self.log_site_error(site.name, "Connection Error", 
                                    "Failed to retrieve data from site. Site may be down or blocking requests.")
                    return None
                cards_df = self.extract_info_simple(soup, site, card_names, strategy)
                if cards_df is None:
                    old_strategy = strategy
                    strategy = (
                        ExternalDataSynchronizer.STRATEGY_SCRAPPER
                        if strategy == ExternalDataSynchronizer.STRATEGY_CRYSTAL
                        else ExternalDataSynchronizer.STRATEGY_CRYSTAL
                    )
                    logger.info(f"Strategy {old_strategy} failed, attempting with {strategy}")
                    cards_df = self.extract_info_simple(soup, site, card_names, strategy)

            if cards_df is None or cards_df.empty:
                self.log_site_error(site.name, "No Data Found", 
                                  f"Strategy '{site.method}' failed to extract any valid card data")
                return None

            if cards_df is not None and not cards_df.empty:
                # Create summary of results
                #self.log_cards_df_stat(site, cards_df)
                total_cards = len(card_names)
                found_cards = cards_df['name'].nunique()
                logger.info(f"Successfully processed {found_cards} cards out of {total_cards} for {site.name}")
                
                if found_cards < total_cards:
                    missing_cards = set(card_names) - set(cards_df['name'].unique())
                    #logger.warning(f"Missing cards for {site.name}: {', '.join(missing_cards)}")
                    logger.warning(f"Missing cards {len(missing_cards)} for {site.name}")

                # Convert DataFrame rows to results
                results = []
                for _, row in cards_df.iterrows():
                    result = {
                        'site_id': site.id,
                        'name': row['name'],
                        'set_name': row['set_name'],
                        'set_code': CardService.get_set_code(row['set_name']),
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
            self.log_site_error(site.name, "Processing Error", str(e))
            return None


    async def search_crystalcommerce_simple(self, site, card_names):
        """
        Simplified version of crystal commerce search that extracts data directly from form elements.
        
        Args:
            site: Site object containing URL and other site info
            card_names: List of card names to search for
        
        Returns:
            BeautifulSoup object containing the parsed HTML response
        """
        search_url = site.url
        
        try:
            # Initial network request
            response_text = await self.network.fetch_url(search_url)
            if not response_text:
                return None
                
            soup = BeautifulSoup(response_text, "html.parser")
            auth_token = await self.network.get_auth_token(soup, site)
            
            if auth_token:
                # Submit search with all card names
                cards_payload = "\r\n".join(card_names)
                payload = {
                    "authenticity_token": auth_token,
                    "query": cards_payload,
                    "submit": "Continue",
                }
                
                response_text = await self.network.post_request(search_url, payload)
                if response_text:
                    return BeautifulSoup(response_text, "html.parser")
                    
            return None
            
        except Exception as e:
            logger.error(f"Error in simplified crystal search for {site.name}: {str(e)}")
            return None

    def extract_info_simple(soup, site, card_names):
        """
        Simplified extraction focusing on form data attributes.
        
        Args:
            soup: BeautifulSoup object containing the parsed HTML
            site: Site object containing site information
            card_names: List of card names to search for
        
        Returns:
            pandas.DataFrame: DataFrame containing the extracted card information
        """
        if soup is None:
            logger.warning(f"Soup is None for site {site.name}")
            return pd.DataFrame()

        cards = []
        seen_variants = set()

        # Find all add-to-cart forms
        forms = soup.find_all("form", {"class": "add-to-cart-form"})
        
        for form in forms:
            try:
                # Extract data from form attributes
                data = form.attrs
                
                # Skip if required attributes are missing
                required_attrs = ['data-name', 'data-price', 'data-category', 'data-variant']
                if not all(attr in data for attr in required_attrs):
                    continue
                
                # Clean and validate card name
                name = clean_card_name(data['data-name'], card_names)
                if not name or name not in card_names:
                    continue
                
                # Parse variant information (quality, language, location)
                variant_parts = data['data-variant'].split(',')
                if len(variant_parts) >= 2:
                    quality = CardQuality.normalize(variant_parts[0].strip())
                    language = CardLanguage.normalize(variant_parts[1].strip())
                else:
                    quality = 'Near Mint'
                    language = 'English'
                
                # Extract price
                price = normalize_price(data['data-price'])
                
                # Create card info dictionary
                card_info = {
                    'name': name,
                    'set_name': data['data-category'],
                    'quality': quality,
                    'language': language,
                    'price': price,
                    'quantity': 1,  # Default quantity if not specified
                    'foil': False,  # Default foil status
                    'version': 'Standard'  # Default version
                }
                
                # Create variant key for deduplication
                variant_key = (
                    card_info['name'],
                    card_info['set_name'],
                    card_info['quality'],
                    card_info['language'],
                    card_info['foil'],
                    card_info['version']
                )
                
                if variant_key not in seen_variants:
                    cards.append(card_info)
                    seen_variants.add(variant_key)
                    
            except Exception as e:
                logger.error(f"Error processing form in {site.name}: {str(e)}")
                continue

        if not cards:
            logger.warning(f"No valid cards found for {site.name}")
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
                df[col] = df[col].astype(dtype)
            
            return df
            
        except Exception as e:
            logger.error(f"Error creating DataFrame for {site.name}: {str(e)}")
            return pd.DataFrame()

    @staticmethod
    def parse_shopify_variant_title(title):
        """Parse title in format 'Card Name [Set Name] Quality [Foil]'"""
        try:
            # Extract set name (content between square brackets)
            set_match = re.search(r'\[(.*?)\]', title)
            if not set_match:
                return None
                
            set_name = set_match.group(1).strip()
            
            # Remove the set name part to process the rest
            remaining = title.split(']')[-1].strip()
            
            # Determine if foil
            is_foil = 'Foil' in remaining
            
            # Extract quality (everything before "Foil" or the end)
            quality = remaining.replace('Foil', '').strip()
            
            return set_name, quality, is_foil
        except Exception as e:
            logger.error(f"Error parsing variant title '{title}': {str(e)}")
            return None

    def extract_info_shopify_json(self, json_data, site, card_names):
        """Extract card information from Shopify API response"""
        cards = []
        
        try:
            for result in json_data:
                searched_card = result.get('searchName')
                if not searched_card or searched_card not in card_names:
                    continue
                    
                products = result.get('products', [])
                for product in products:
                    # Basic product info
                    name = product.get('name')
                    set_name = product.get('setName')
                    collector_number = product.get('collectorNumber')
                    
                    # Process variants
                    variants = product.get('variants', [])
                    for variant in variants:
                        # Skip if no quantity available
                        quantity = variant.get('quantity', 0)
                        if quantity <= 0:
                            continue
                            
                        # Get variant details
                        title = variant.get('title', '').lower()
                        price = float(variant.get('price', 0.0))
                        
                        # Determine foil status
                        is_foil = 'foil' in title
                        
                        # Extract quality
                        quality = 'Near Mint'  # Default
                        if 'near mint' in title or 'nm' in title:
                            quality = 'Near Mint'
                        elif 'lightly played' in title or 'lp' in title:
                            quality = 'Lightly Played'
                        elif 'moderately played' in title or 'mp' in title:
                            quality = 'Moderately Played'
                        elif 'heavily played' in title or 'hp' in title:
                            quality = 'Heavily Played'
                        elif 'damaged' in title or 'dmg' in title:
                            quality = 'Damaged'
                        
                        card_info = {
                            'name': name,
                            'set_name': set_name,
                            'foil': is_foil,
                            'quality': quality,
                            'language': 'English',  # Default for Shopify stores
                            'quantity': quantity,
                            'price': price,
                            'version': 'Standard',
                            'collector_number': collector_number,
                            'set_code': product.get('setCode', '')
                        }
                        
                        cards.append(card_info)
                        
            if not cards:
                logger.warning(f"No valid cards found in Shopify response for {site.name}")
                return pd.DataFrame()
                
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
                df[col] = df[col].astype(dtype)
            
            # Normalize quality and language values
            df['quality'] = df['quality'].apply(CardQuality.normalize)
            df['language'] = df['language'].apply(CardLanguage.normalize)
            
            return df
            
        except Exception as e:
            logger.error(f"Error processing Shopify JSON for {site.name}: {str(e)}")
            return pd.DataFrame()


    async def search_shopify(self, site, card_names):
        """Get card data from Shopify via Binder API"""
        try:
            # Format the payload
            payload = [{"card": name, "quantity": 1} for name in card_names]
            
            # Construct API URL
            store_url = site.url.replace('https://', '').replace('http://', '')
            if store_url.endswith('/'):
                store_url = store_url[:-1]
            
            initial_url = site.url
            response_text = await self.network.fetch_url(initial_url)
            #api_url = f"https://api.binderpos.com/external/shopify/decklist?storeUrl={store_url}&type=mtg"
            
            # Make the request
            # Submit the decklist
            submit_url = f"{site.url}"
            response = await self.network.post_request(submit_url, payload)
            
            if not response:
                logger.error(f"Failed to submit decklist to {site.name}")
                return None
                
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON response from {site.name}")
                return None
                
        except Exception as e:
            logger.error(f"Error searching Hawk site {site.name}: {str(e)}")
            return None

    async def extract_info_hawk_json(self, response_json, site, card_names):
        """Extract card information directly from Hawk JSON response"""
        if not response_json:
            logger.warning(f"No JSON response from {site.name}")
            return pd.DataFrame()
            
        cards = []
        try:
            # Process each search result
            for search_result in response_json:
                searched_card = search_result.get('searchName')
                if not searched_card or searched_card not in card_names:
                    continue
                    
                products = search_result.get('products', [])
                for product in products:
                    # Basic product info
                    name = product.get('name')
                    set_name = product.get('setName')
                    variants = product.get('variants', [])
                    
                    for variant in variants:
                        # Skip if no quantity available
                        quantity = variant.get('quantity', 0)
                        if quantity <= 0:
                            continue
                            
                        # Get variant details
                        price = float(variant.get('price', 0.0))
                        
                        # Parse condition and finish from title
                        title = variant.get('title', '').lower()
                        
                        # Determine if foil
                        is_foil = 'foil' in title
                        
                        # Extract condition
                        quality = 'Near Mint'  # Default
                        if 'near mint' in title or 'nm' in title:
                            quality = 'Near Mint'
                        elif 'lightly played' in title or 'lp' in title:
                            quality = 'Lightly Played'
                        elif 'moderately played' in title or 'mp' in title:
                            quality = 'Moderately Played'
                        elif 'heavily played' in title or 'hp' in title:
                            quality = 'Heavily Played'
                        elif 'damaged' in title or 'dmg' in title:
                            quality = 'Damaged'
                            
                        card_info = {
                            'name': name,
                            'set_name': set_name,
                            'foil': is_foil,
                            'quality': quality,
                            'language': 'English',  # Default for most stores
                            'quantity': quantity,
                            'price': price,
                            'version': 'Standard',
                            'set_code': product.get('setCode', ''),
                            'collector_number': product.get('collectorNumber', '')
                        }
                        
                        # Add to cards list if valid
                        if all(key in card_info for key in ['name', 'set_name', 'quality', 'quantity', 'price']):
                            cards.append(card_info)
                        
            if not cards:
                logger.warning(f"No valid cards found in Hawk response for {site.name}")
                return pd.DataFrame()
                
            # Convert to DataFrame
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
                df[col] = df[col].astype(dtype)
            
            # Normalize quality and language values
            df['quality'] = df['quality'].apply(CardQuality.normalize)
            df['language'] = df['language'].apply(CardLanguage.normalize)
            
            return df
            
        except Exception as e:
            logger.error(f"Error processing Hawk JSON for {site.name}: {str(e)}")
            return pd.DataFrame()
    
    async def search_hawk(self, site, card_names):
        """Submit decklist and get results from Hawk site"""
        try:
            # Format the decklist as expected by the site
            decklist = "\n".join(card_names)
            
            # Prepare the form data
            payload = {
                'decklist': decklist,
                'resultsSort': 'score',
                'inStock': 'Y',
                'inclBasicLands': 'N'  # Usually don't need basic lands
            }
            
            # First make a GET request to get any necessary tokens/cookies
            initial_url = site.url
            response_text = await self.network.fetch_url(initial_url)
            
            if not response_text:
                logger.error(f"Failed to get initial page for {site.name}")
                return None
                
            # Submit the decklist
            submit_url = f"{site.url}/deck-results/"
            response = await self.network.post_request(submit_url, payload)
            
            if not response:
                logger.error(f"Failed to submit decklist to {site.name}")
                return None
                
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON response from {site.name}")
                return None
                
        except Exception as e:
            logger.error(f"Error searching Hawk site {site.name}: {str(e)}")
            return None

    @staticmethod
    def detect_foil(product_foil=None, product_version=None, variant_data=None):
        """Unified foil detection logic
        Args:
            product_foil (str): Foil information from product
            product_version (str): Version information that might contain foil info
            variant_data (str): Additional variant data that might indicate foil
        Returns:
            bool: True if card is foil, False otherwise
        """
        if not any([product_foil, product_version, variant_data]):
            return False
            
        check_strings = [
            s.lower() for s in [product_foil, product_version, variant_data]
            if s is not None
        ]
        
        return any('foil' in s for s in check_strings)

    @staticmethod
    def strategy_crystal(card, variant):
        if "no-stock" in variant.get("class", []) or "0 In Stock" in variant:
            return None

        form_element = variant.find("form", {"class": "add-to-cart-form"})
        if not form_element:
            return None

        attributes = form_element.attrs
        if "data-name" not in attributes:
            return None

        unclean_name, product_version, product_foil = ExternalDataSynchronizer.find_name_version_foil(attributes["data-name"])
        
        # Use unified foil detection
        is_foil = ExternalDataSynchronizer.detect_foil(
            product_foil=product_foil,
            product_version=product_version,
            variant_data=attributes.get("data-variant", "")
        )

        quality_language = ExternalDataSynchronizer.normalize_variant_description(attributes["data-variant"])
        quality, language = quality_language[:2]
        quality = CardQuality.normalize(quality)
        language = CardLanguage.normalize(language)

        select_tag = variant.find("select", {"class": "qty"}) or variant.find("input", {"class": "qty"})
        qty_available = select_tag["max"] if select_tag and "max" in select_tag.attrs else "0"

        if isinstance(card, dict):
            card_data = card.copy()
            card_data.update({
                'quality': quality,
                'language': language,
                'quantity': int(qty_available),
                'set_name': attributes["data-category"],
                'price': normalize_price(attributes["data-price"]),
                'foil': is_foil
            })
            return card_data
        else:
            card.quality = quality
            card.language = language
            card.quantity = int(qty_available)
            card.set_name = attributes["data-category"]
            card.price = normalize_price(attributes["data-price"])
            card.foil = is_foil
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
                
            quality = CardQuality.normalize(quality)  # Normalize quality here
            language = CardLanguage.normalize(language)  # Add this line

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
    def find_name_version_foil(place_holder):
        """Improved version/foil detection"""
        items = re.split(r" - ", place_holder)
        items = [x.strip() for x in items]
        product_name = items[0]
        product_version = ""
        product_foil = ""

        for item in items[1:]:
            item_lower = item.lower()
            if "foil" in item_lower:
                product_foil = item
                # If version is part of foil string, extract it
                version_part = re.sub(r'\bfoil\b', '', item, flags=re.IGNORECASE).strip()
                if version_part:
                    product_version = version_part
            elif item:
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
                quality = CardQuality.normalize(raw_quality)
                language = CardLanguage.normalize(raw_language)
                
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
        
#old
    # @staticmethod
    # def convert_foil_to_bool(foil_value):
    #     """Convert foil value to boolean based on CardVersion"""
    #     if isinstance(foil_value, bool):
    #         return foil_value
    #     if isinstance(foil_value, str):
    #         return foil_value.lower() in [CardVersion.FOIL.value.lower(), 'true', '1', 'yes']
    #     return False

    # @classmethod
    # async def update_all_cards(cls):
    #     card_query = (
    #         UserBuylistCard.query.with_entities(
    #             UserBuylistCard.name).distinct().all()
    #     )
    #     card_names = [card.name for card in card_query]
    #     sites = Site.query.filter_by(active=True).all()

    #     async with cls() as fetcher:
    #         tasks = [fetcher.process_site(site, card_names) for site in sites]
    #         await asyncio.gather(*tasks)

    # @staticmethod
    # def extract_info(soup, site, card_names, strategy=STRATEGY_CRYSTAL):
    #     """Extract card info from the provided HTML soup using the given strategy."""
    #     if soup is None:
    #         logger.warning(f"Soup is None for site {site.name}")
    #         return pd.DataFrame()

    #     cards = []
    #     seen_variants = set()

    #     excluded_categories = {
    #         "playmats",
    #         "booster packs",
    #         "booster box",
    #         "mtg booster boxes",
    #         "art series",
    #         "fat packs and bundles",
    #         "mtg booster packs",
    #         "magic commander deck",
    #         "world championship deck singles",
    #         "The Crimson Moon's Fairy Tale",
    #         "rpg accessories",
    #         "scan other",
    #         "intro packs and planeswalker decks",
    #         "wall scrolls",
    #     }

    #     content = soup.find(
    #         "div", {"class": ["content", "content clearfix",
    #                           "content inner clearfix"]}
    #     )
    #     if content is None:
    #         logger.error(f"Content div not found for site {site.name}")
    #         return pd.DataFrame()

    #     products_containers = content.find_all(
    #         "div", {"class": "products-container browse"}
    #     )
    #     if not products_containers:
    #         logger.warning(f"No products container found for site {site.name}")
    #         return pd.DataFrame()

    #     required_fields = {
    #         'name',
    #         'set_name',
    #         'quality',
    #         'language',
    #         'quantity',
    #         'price',
    #         'version',
    #         'foil'
    #     }

    #     logger.info(f"Processing container for {site.name}")
    #     for container in products_containers:
    #         logger.debug(f"Container HTML: {container.prettify()}")
            
    #         items = container.find_all("li", {"class": "product"})
    #         logger.debug(f"Found {len(items)} product items in {site.name}")
            
    #         for item in items:
    #             try:
    #                 logger.debug(f"Processing item in {site.name}: {item.get('id', 'no-id')}")
    #                 card_attrs = ExternalDataSynchronizer.process_product_item(
    #                     item, site, card_names, excluded_categories
    #                 )
    #                 if card_attrs:
    #                     logger.debug(f"Valid card found in {site.name}: {card_attrs['name']}") 
    #                     if all(key in card_attrs for key in required_fields):
    #                         ExternalDataSynchronizer.process_variants(
    #                             item, card_attrs, cards, seen_variants, strategy
    #                         )
    #                     else:
    #                         missing = required_fields - set(card_attrs.keys())
    #                         logger.warning(f"Missing fields {missing} for card in {site.name}")
    #                 else:
    #                     logger.debug(f"Invalid card item in {site.name}")
    #             except Exception as e:
    #                 logger.exception(f"Error processing item in {site.name}")
    #                 continue

    #     if not cards:
    #         logger.warning(f"No valid cards found in container for {site.name}")
    #         return pd.DataFrame()

    #     try:
    #         df = pd.DataFrame(cards)
    #         # Ensure standard column names and data types
    #         standard_columns = {
    #             'name': str,
    #             'set_name': str,
    #             'price': float,
    #             'version': str,
    #             'foil': bool,
    #             'quality': str,
    #             'language': str,
    #             'quantity': int
    #         }
            
    #         # Add missing columns with default values
    #         for col, dtype in standard_columns.items():
    #             if col not in df.columns:
    #                 df[col] = dtype()
    #             df[col] = df[col].astype(dtype)
            
    #         # Normalize quality and language values
    #         df['quality'] = df['quality'].apply(CardQuality.normalize)
    #         df['language'] = df['language'].apply(CardLanguage.normalize)
    #         df['version'] = df['version'].apply(CardVersion.normalize)
            
    #         return df
            
    #     except Exception as e:
    #         logger.error(f"Error creating DataFrame for {site.name}: {str(e)}")
    #         return pd.DataFrame()

    # @staticmethod
    # def extract_info_shopify(soup, site, card_names):
    #     """Extract card info from Shopify site HTML structure including variants."""
    #     if soup is None:
    #         logger.warning(f"Soup is None for site {site.name}")
    #         return pd.DataFrame()

    #     cards = []
    #     seen_variants = set()

    #     results_container = soup.find("div", {"class": "results-container "})
    #     if not results_container:
    #         logger.warning(f"No results container found for site {site.name} \n\n\n{soup}  \n\n\n")
    #         return pd.DataFrame()

    #     result_wrappers = results_container.find_all("div", {"class": "result-found-wrapper"})
    #     if not result_wrappers:
    #         logger.warning(f"No result wrappers found for site {site.name} \n\n\n{soup}\n\n\n")
    #         return pd.DataFrame()

    #     for wrapper in result_wrappers:
    #         try:
    #             card_title = wrapper.find("p", {"class": "result-card-title"}).text.strip()

    #             # Process each item container
    #             for item_container in wrapper.find_all("div", {"class": "result-item-container"}):
    #                 # Find variant switch container
    #                 variant_container = item_container.find("div", {"class": "item-switch-add-container"})
    #                 if variant_container:
    #                     # Process each variant option
    #                     for variant_option in variant_container.find_all("div", {"class": "variant-switch-add-option"}):
    #                         try:
    #                             # Extract variant details
    #                             title = variant_option.find("p").get("title", "").strip()
    #                             quantity = variant_option.find_all("p")[1].text.strip()
    #                             price = variant_option.find_all("p")[2].text.strip()

    #                             # Parse quantity (format: "xN")
    #                             qty = int(re.search(r'x(\d+)', quantity).group(1))
                                
    #                             # Parse price (format: "$X.XX CAD")
    #                             price_value = float(re.search(r'\$(\d+\.\d+)', price).group(1))

    #                             # Extract card name (everything before the first '[')
    #                             card_name = title.split('[')[0].strip()
                                
    #                             # Skip if card not in requested list
    #                             if card_name not in card_names:
    #                                 continue

    #                             # Parse variant title
    #                             parsed_info = ExternalDataSynchronizer.parse_shopify_variant_title(title)
    #                             if not parsed_info:
    #                                 continue
                                    
    #                             set_name, quality, is_foil = parsed_info

    #                             card_info = {
    #                                 'name': card_name,
    #                                 'set_name': set_name,
    #                                 'foil': is_foil,
    #                                 'quality': quality,
    #                                 'language': 'English',  # Assuming English
    #                                 'quantity': qty,
    #                                 'price': price_value,
    #                                 'version': 'Standard'
    #                             }

    #                             # Create variant key
    #                             variant_key = (
    #                                 card_info['name'],
    #                                 card_info['set_name'],
    #                                 card_info['quality'],
    #                                 card_info['language'],
    #                                 card_info['foil'],
    #                                 card_info['version']
    #                             )

    #                             if variant_key not in seen_variants:
    #                                 cards.append(card_info)
    #                                 seen_variants.add(variant_key)

    #                         except Exception as e:
    #                             logger.error(f"Error processing variant option in {site.name}: {str(e)}")
    #                             continue

    #         except Exception as e:
    #             logger.exception(f"Error processing wrapper in {site.name}")
    #             continue

    #     if not cards:
    #         logger.warning(f"No valid cards found in container for {site.name}")
    #         return pd.DataFrame()

    #     try:
    #         df = pd.DataFrame(cards)
    #         # Ensure standard column names and data types
    #         standard_columns = {
    #             'name': str,
    #             'set_name': str,
    #             'price': float,
    #             'version': str,
    #             'foil': bool,
    #             'quality': str,
    #             'language': str,
    #             'quantity': int
    #         }
            
    #         # Add missing columns with default values
    #         for col, dtype in standard_columns.items():
    #             if col not in df.columns:
    #                 df[col] = dtype()
    #             df[col] = df[col].astype(dtype)
            
    #         # Normalize quality and language values
    #         df['quality'] = df['quality'].apply(CardQuality.normalize)
    #         df['language'] = df['language'].apply(CardLanguage.normalize)
            
    #         return df
            
    #     except Exception as e:
    #         logger.error(f"Error creating DataFrame for {site.name}: {str(e)}")
    #         return pd.DataFrame()

    # @staticmethod
    # def process_product_item(item, site, card_names, excluded_categories):
    #     """Fixed dict handling with better HTML inspection"""
    #     try:
    #         logger.debug(f"Starting process_product_item for {site.name}")
            
    #         if ExternalDataSynchronizer.is_yugioh_card(item):
    #             logger.debug(f"Skipping Yugioh card in {site.name}")
    #             return None

    #         # Debug HTML structure
    #         logger.debug(f"Product HTML in {site.name}: {item.prettify()}")

    #         meta = item.find("div", {"class": "meta"})
    #         if not meta:
    #             logger.warning(f"No meta div found for item in {site.name}")
    #             return None
            
    #         logger.debug(f"Meta div in {site.name}: {meta.prettify()}")
                
    #         category_span = meta.find("span", {"class": "category"})
    #         name_header = meta.find("h4", {"class": "name"})
            
    #         if not category_span or not name_header:
    #             logger.warning(f"Missing category or name header in {site.name}")
    #             logger.debug(f"Category span: {category_span}")
    #             logger.debug(f"Name header: {name_header}")
    #             return None
                
    #         test_category = category_span.text.strip()
    #         test_title = name_header.text.strip()
            
    #         logger.debug(f"Found card: '{test_title}' in category: '{test_category}' for {site.name}")

    #         if any(cat in test_category.lower() for cat in excluded_categories):
    #             logger.debug(f"Category {test_category} is in excluded list for {site.name}")
    #             return None

    #         # Create a dictionary with standardized keys (all lowercase)
    #         card_info = {
    #             'name': '',
    #             'set_name': test_category,
    #             'foil': False,
    #             'quality': 'Near Mint',
    #             'language': 'English',
    #             'quantity': 0,
    #             'price': 0.0,
    #             'version': 'Standard'
    #         }

    #         parsed_card = parse_card_string(test_title)
    #         logger.debug(f"Parsed card result for {site.name}: {parsed_card}")
            
    #         if isinstance(parsed_card, dict):
    #             # Update key mapping to handle both old and new formats
    #             key_mapping = {
    #                 'Name': 'name',
    #                 'Foil': 'foil',
    #                 'Edition': 'set_name',
    #                 'Quality': 'quality',
    #                 'Language': 'language',
    #                 'Quantity': 'quantity',
    #                 'Price': 'price',
    #                 'Version': 'version'
    #             }
                
    #             for old_key, new_key in key_mapping.items():
    #                 if old_key in parsed_card:
    #                     card_info[new_key] = parsed_card[old_key]
    #         else:
    #             logger.debug(f"Parsed card is object with name: {getattr(parsed_card, 'name', None)}")
    #             # Handle object-style parsing result
    #             card_info['name'] = getattr(parsed_card, 'name', test_title)
    #             card_info['foil'] = getattr(parsed_card, 'foil', False)

    #         # Clean and validate card name
    #         original_name = card_info['name']  
    #         card_info['name'] = clean_card_name(card_info['name'], card_names)  
    #         logger.debug(f"Card name cleaned from '{original_name}' to '{card_info['name']}' for {site.name}")

    #         if not card_info['name']: 
    #             logger.warning(f"Card name cleaned to empty string in {site.name}")
    #             return None
                
    #         if (card_info['name'] not in card_names and  
    #             card_info['name'].split(" // ")[0].strip() not in card_names):
    #             logger.debug(f"Card '{card_info['name']}' not in requested list for {site.name}")
    #             logger.debug(f"Available card names: {card_names}")
    #             return None

    #         logger.debug(f"Successfully processed card '{card_info['name']}' for {site.name}")  
    #         return card_info

    #     except Exception as e:
    #         logger.exception(f"Error in process_product_item for {site.name}")
    #         logger.error(f"Full error: {str(e)}")
    #         logger.error(f"Item HTML: {item.prettify() if item else 'None'}")
    #         return None

    # @staticmethod
    # def process_variants(item, card, cards, seen_variants, strategy):
    #     variants = item.find("div", {"class": "variants"})
    #     for variant in variants.find_all("div", {"class": "variant-row"}):
            
    #         card_variant = (
    #             ExternalDataSynchronizer.strategy_crystal(card, variant)
    #             if strategy == ExternalDataSynchronizer.STRATEGY_CRYSTAL
    #             else ExternalDataSynchronizer.strategy_scrapper(card, variant)
    #         )
    #         if card_variant is not None:
    #             # Create a hashable key from the variant's relevant data
    #             variant_key = (
    #                 card_variant.get('name', ''),
    #                 card_variant.get('set_name', ''),
    #                 card_variant.get('quality', ''),
    #                 card_variant.get('language', ''),
    #                 card_variant.get('foil', False),
    #                 card_variant.get('version', 'Standard')
    #             )
    #             if variant_key not in seen_variants:
    #                 cards.append(card_variant)
    #                 seen_variants.add(variant_key)

    # @staticmethod
    # def is_yugioh_card(item):
    #     image = item.find("div", {"class": "image"})
    #     a_tag = image and image.find("a", href=True)
    #     return a_tag and "yugioh" in a_tag["href"]
