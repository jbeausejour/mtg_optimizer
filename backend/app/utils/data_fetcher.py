import asyncio
import logging
import re
from concurrent.futures import ThreadPoolExecutor
import json
import time
import traceback
import pandas as pd
from bs4 import BeautifulSoup
from threading import Lock

import urllib


from app.extensions import db
from app.constants import CardLanguage, CardQuality, CardVersion
from app.services import CardService
from app.utils.helpers import (
    clean_card_name,
    extract_numbers,
    normalize_price,
    parse_card_string
)
from app.utils.selenium_driver import NetworkDriver

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
    SCRAPPING_METHOD_CRYSTAL = 1
    SCRAPPING_METHOD_SCRAPPER = 2
    SCRAPPING_METHOD_HAWK = 3
    SCRAPPING_METHOD_SHOPIFY = 4
    SCRAPPING_METHOD_OTHER = 5
    scrapping_method_dict = {
        "crystal": SCRAPPING_METHOD_CRYSTAL,
        "scrapper": SCRAPPING_METHOD_SCRAPPER,
        "hawk": SCRAPPING_METHOD_HAWK,
        "shopify": SCRAPPING_METHOD_SHOPIFY,
        "other": SCRAPPING_METHOD_OTHER,
    }

    def __init__(self):
        self.network = NetworkDriver()
        self.error_collector = ErrorCollector.get_instance()
        self.error_collector.reset()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass 

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

    async def scrape_multiple_sites(self, sites, card_names):
        """Enhanced scraping with proper Selenium integration"""
        start_time = time.time()  # Start timing
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
                # Aggressive batching settings
                MAX_CONCURRENT = 20  # Much higher concurrent limit
                BATCH_SIZE = min(max(len(sites) // 2, 10), 30)  # Larger batch size, between 10-30
                total_batches = (len(tasks) + BATCH_SIZE - 1) // BATCH_SIZE
                
                for batch_num, i in enumerate(range(0, len(tasks), BATCH_SIZE), 1):
                    try:
                        logger.info(f"Processing batch {batch_num}/{total_batches}")
                        batch = tasks[i:i + BATCH_SIZE]
                        batch_results = await asyncio.gather(*batch, return_exceptions=True)
                        
                        for result in batch_results:
                            if isinstance(result, Exception):
                                logger.error(f"Batch processing error: {str(result)}", exc_info=True)
                            elif result:
                                results.extend(result)
                                #logger.info(f"Processed batch {batch_num}/{total_batches} ({len(result)}/{len(results)})")
                                
                    except Exception as e:
                        logger.error(f"Error processing batch {batch_num}: {str(e)}", exc_info=True)
                        
                elapsed_time = round(time.time() - start_time, 2)  # Compute elapsed time
                logger.info(f"Completed scraping with {len(results)} total results in {elapsed_time} seconds")
                return results
                
            except Exception as e:
                logger.error(f"Fatal error in scrape_multiple_sites: {str(e)}", exc_info=True)
                raise

    async def process_site(self, site, card_names):
        """Process a single site and return results without saving to DB"""
        start_time = time.time()  # Start timing
        scrapping_method = ExternalDataSynchronizer.scrapping_method_dict.get(site.method.lower(), 
                                    ExternalDataSynchronizer.SCRAPPING_METHOD_CRYSTAL)
        
        logger.info(f"Processing site: {site.name}")
        logger.info(f"\t o Strategy: {site.method}")
        logger.info(f"\t o URL: {site.url}")
        if site.api_url:
            logger.info(f"\t o API URL: {site.api_url}")

        try:
            if scrapping_method == ExternalDataSynchronizer.SCRAPPING_METHOD_SHOPIFY:
                # Get data from Shopify API
                json_data = await self.search_shopify(site, card_names)
                
                if not json_data:
                    self.error_collector.unreachable_stores.add(site.name)
                    self.log_site_error(site.name, "Connection Error", 
                                    "Failed to retrieve data from Shopify API.")
                    return None
                    
                cards_df = self.extract_info_shopify_json(json_data, site, card_names)
                
            elif scrapping_method == ExternalDataSynchronizer.SCRAPPING_METHOD_HAWK:
                
                json_data = await self.search_hawk(site, card_names)
            
                if not json_data:
                    self.error_collector.unreachable_stores.add(site.name)
                    self.log_site_error(site.name, "Connection Error", 
                                    "Failed to retrieve data from Hawk API.")
                    return None
                    
                cards_df = self.extract_info_hawk_json(json_data, site, card_names)
                
            else:
                soup = await self.search_crystalcommerce(site, card_names)
                if not soup:
                    self.error_collector.unreachable_stores.add(site.name)
                    self.log_site_error(site.name, "Connection Error", 
                                    "Failed to retrieve data from site. Site may be down or blocking requests.")
                    return None
                cards_df = self.extract_info_crystal(soup, site, card_names, scrapping_method)
                if cards_df.empty:
                    old_strategy = scrapping_method
                    scrapping_method = (
                        ExternalDataSynchronizer.SCRAPPING_METHOD_SCRAPPER
                        if scrapping_method == ExternalDataSynchronizer.SCRAPPING_METHOD_CRYSTAL
                        else ExternalDataSynchronizer.SCRAPPING_METHOD_CRYSTAL
                    )
                    logger.info(f"Strategy {old_strategy} failed, attempting with {scrapping_method}")
                    cards_df = self.extract_info_crystal(soup, site, card_names, scrapping_method)

            if cards_df is None or cards_df.empty:
                self.log_site_error(site.name, "No Data Found", 
                                  f"Strategy '{site.method}' failed to extract any valid card data")
                return None

            if cards_df is not None and not cards_df.empty:
                # Create summary of results
                #self.log_cards_df_stat(site, cards_df)
                total_cards = len(card_names)
                found_cards = cards_df['name'].nunique()
                elapsed_time = round(time.time() - start_time, 2)  # Compute elapsed time

                logger.info(f"Successfully processed {found_cards} / {total_cards} (Total: {len(cards_df)}) for {site.name} in {elapsed_time} seconds")
                
                # if found_cards < total_cards:
                #     missing_cards = set(card_names) - set(cards_df['name'].unique())
                #     #logger.warning(f"Missing cards for {site.name}: {', '.join(missing_cards)}")
                #     logger.warning(f"Missing cards {len(missing_cards)} for {site.name}")

                # Convert DataFrame rows to results
                results = []
                for _, row in cards_df.iterrows():
                    result = {
                        'site_id': site.id,
                        'name': row['name'],
                        'set_name': row['set_name'],
                        'set_code': CardService.get_clean_set_code(row['set_name']),
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
            elapsed_time = round(time.time() - start_time, 2)
            self.log_site_error(site.name, f"Processing Error (after {elapsed_time} seconds)", str(e))
            return None

    @staticmethod
    def extract_magic_set(url):
        try:
            # Split the URL into parts
            parts = url.split('/')

            # Find the part that contains the set information
            for part in parts:
                if "singles-" in part:  # Look for the part with "singles-"
                    # Remove the prefix up to "singles-", suffix like "-brawl", and replace underscores with spaces
                    return (
                        part.split("singles-")[-1]  # Extract after "singles-"
                        .replace("-brawl", "")
                        .replace("_", " ")
                )
                
        except Exception as e:
            logger.error(f"Fatal error in extract_magic_set: {str(e)}", exc_info=True)
            return None
                

    def extract_info_crystal(self, soup, site, card_names, scrapping_method):
        """
        Extract card information using either form-based or scrapper scrapping_method.
        """
        
        excluded_categories = {
            "playmats",
            "booster packs",
            "booster box",
            "cb consignment",
            "mtg booster boxes",
            "art series",
            "fat packs and bundles",
            "mtg booster packs",
            "magic commander deck",
            "world championship deck singles",
            "the crimson moon's fairy tale",
            "rpg accessories",
            "scan other",
            "intro packs and planeswalker decks",
            "wall scrolls",
            "lots of keycards",
            "board games",
            "token colorless",
            "scan other",
            "books",
            "pbook",
            "dice",
            "pathfinder",
            "promos: miscellaneous",
            "brawl",
        }
        promo_set_mappings = {
            'CBL Bundle Promo': 'Commander Legends: Battle for Baldur\'s Gate',
            'Treasure Chest Promo': 'ixalan promos',
            'Bundle Promo': 'Promo Pack',  # Generic bundle promos
        }

        if soup is None:
            logger.warning(f"Soup is None for site {site.name}")
            return pd.DataFrame()

        cards = []
        seen_variants = set()

        if scrapping_method == self.SCRAPPING_METHOD_CRYSTAL:
            # Form-based extraction focusing on add-to-cart forms
            forms = soup.find_all("form", {"class": "add-to-cart-form"})
            if not forms:
                logger.warning(f"No add-to-cart forms found for site {site.name}")
                forms = soup.find_all("form", {"class": "add-to-cart-form"})

            for form in forms:
                try:                
                    product = form.find_parent("li", {"class": "product"})
                    if not product:
                        logger.info(f"Could not find parent product container for form {form}")
                        continue
                        
                    # Check if it's a Magic card
                    if not self.is_magic_card(product):
                        logger.debug(f"Skipping non-Magic card product")
                        continue
                    # Extract data from form attributes
                    data = form.attrs
                    
                    # Skip if required attributes are missing
                    required_attrs = ['data-name', 'data-price', 'data-category', 'data-variant']
                    if not all(attr in data for attr in required_attrs):
                        continue

                    current_card = parse_card_string(data['data-name'])
                    if not current_card:
                        continue

                    # Clean and validate card name
                    name = clean_card_name(current_card["Name"], card_names)
                    # logger.info(f"after clean_card_name form: {name} ")
                    if not name or (name not in card_names and name.split(" // ")[0].strip() not in card_names):
                        continue

                    category = data.get('data-category')
                    set_name = category
                    # logger.info(f"after data.get('data-category') form: {set_name} ")

                    if any(test in category.lower() for test in excluded_categories):
                        if category == 'Brawl':
                            product_link = form.find_previous("a", itemprop="url")
                            # logger.info(f"product_link: {product_link} for site: {site.name}\n {category}")
                        
                            if product_link:
                                product_url = product_link.get("href")
                                set_name = self.extract_magic_set(product_url)
                                # logger.info(f"product_url: {product_url} for site: {site.name}\n {set_name}")
                        elif category == 'Promos: Miscellaneous':
                            card_name = data.get('data-name', '')
                            name_parts = card_name.split(' - ')
                            promo_suffix = name_parts[-1] if len(name_parts) > 1 else None
                            if promo_suffix and promo_suffix in promo_set_mappings:
                             set_name =  promo_set_mappings[promo_suffix]

                        continue

                    # Try to match with closest set name using CardService
                    set_name = CardService.get_closest_set_name(set_name)
                    if not set_name or set_name.lower() == "unknown":
                        logger.info(f"after get_closest_set_name: {set_name} for site: {site.name}\n {data}")
                        continue
                    # logger.info(f"after get_closest_set_name form: {set_name} ")
                    set_code = CardService.get_clean_set_code(set_name)
                    if not set_code or set_code.lower() == "unknown":
                        logger.info(f"after get_clean_set_code: {set_code} for site: {site.name}\n {data}")
                        continue
                    if set_code.lower() == "pbook":
                        logger.info(f"after pbook: {set_code} name:{set_name} for site: {site.name}\n data: {data}\n {data}")
                        continue
                    # logger.info(f"after get_clean_set_code form: {set_code} ")

                    test = data.get('data-variant', '').strip()
                    if not test:
                        continue

                    quality, language = self.extract_quality_language(test)
                    # logger.info(f"after extract_quality_language form: {quality} ")
                    
                    # Parse name, version, and foil status
                    unclean_name, version, foil = self.find_name_version_foil(data['data-name'])
                    is_foil = self.detect_foil(product_foil=foil, product_version=version, variant_data=test)
                    version = CardVersion.normalize(version or 'Standard')

                    # Extract and validate quantity
                    quantity = self.extract_quantity(form)
                    if not quantity or quantity <= 0:
                        quantity = 1

                    # Create card info dictionary
                    card_info = {
                        'name': name,
                        'set_name': set_name,
                        'set_code': set_code,
                        'quality': quality,
                        'language': language,
                        'price': normalize_price(data['data-price']),
                        'quantity': quantity,
                        'foil': is_foil,
                        'version': version
                    }
                    
                    # Create variant key for deduplication
                    variant_key = (
                        card_info['name'],
                        card_info['set_name'],
                        card_info['set_code'],
                        card_info['quality'],
                        card_info['language'],
                        card_info['foil'],
                        card_info['version']
                    )
                    
                    if variant_key not in seen_variants:
                        cards.append(card_info)
                        seen_variants.add(variant_key)
                        
                except Exception as e:
                    logger.error(f"Error processing form in {site.name}: {str(e)}", exc_info=True)
                    continue

        else:
            # Original scrapper strategy with enhanced validation
            content = soup.find("div", {"class": ["content", "content clearfix", "content inner clearfix"]})
            if content is None:
                logger.error(f"Content div not found for site {site.name}")
                return pd.DataFrame()

            products_containers = content.find_all("div", {"class": "products-container browse"})
            if not products_containers:
                logger.warning(f"No variants container found for site {site.name}")
                return pd.DataFrame()

            for container in products_containers:
                products = container.find_all("li", {"class": "product"})
                for product in products:
                    if not self.is_magic_card(product):
                        logger.debug(f"Skipping non-Magic card product")
                        continue
                    variants_section = product.find("div", {"class": "variants"})
                    if not variants_section:
                        continue

                    for variant in variants_section.find_all("div", {"class": "variant-row"}):
                        if "no-stock" in variant.get("class", []):
                            continue
                        try:
                            # Extract and validate quality and language
                            variant_data = variant.find(
                                "span", {"class": "variant-short-info variant-description"}
                            ) or variant.find("span", {"class": "variant-short-info"})
                            
                            if not variant_data:
                                continue
                            
                            # Get set name
                            meta_div = product.find("div", {"class": "meta"})
                            if not meta_div:
                                logger.warning(f"Meta div not found for variant")
                                continue

                            # Get and validate name
                            name_header = meta_div.find("h4", {"class": "name"}) if meta_div else None
                            if not name_header:
                                logger.warning(f"Name header not found for variant")
                                continue

                            parsed_card = parse_card_string(name_header.text)
                            if not parsed_card:
                                logger.warning(f"Failed to parse card name: {name_header.text}")
                                continue

                            clean_name = clean_card_name(parsed_card.get('Name', name_header.text), card_names)
                            if not clean_name or (
                                clean_name not in card_names and 
                                clean_name.split(" // ")[0].strip() not in card_names
                                ):
                                logger.warning(f"Invalid card name: {clean_name}")
                                continue

                            # Extract and validate quality and language
                            quality_language = ExternalDataSynchronizer.normalize_variant_description(
                                variant_data.text
                            )
                            # logger.info(f"after normalize_variant_description: {quality_language}")
                            quality, language = self.extract_quality_language(quality_language)

                            if not quality or not language:
                                logger.warning(f"Quality or language not found for variant{quality_language}")
                                continue

                            # Extract and validate quantity
                            quantity = self.extract_quantity(variant)
                            if quantity is None or quantity <= 0:
                                logger.warning(f"Invalid quantity for variant: {quantity}")
                                continue

                            # Extract and validate price
                            price = self.extract_price(variant)
                            if price is None or price <= 0:
                                logger.warning(f"Invalid price for variant: {price}")
                                continue

                            set_elem = meta_div.find("span", {"class": "category"}) if meta_div else None
                            if not set_elem:
                                logger.warning(f"Set element not found for variant")
                                continue
                            
                            if any(cat in set_elem.text.lower() for cat in excluded_categories):
                                logger.warning(f"Excluded category found: {set_elem.text}")
                                continue

                            set_name = CardService.get_closest_set_name(set_elem.text.lower())
                            if not set_name:
                                logger.warning(f"Failed to get set name for variant: {set_elem.text}")
                                continue
                            set_code = CardService.get_clean_set_code(set_name)
                            if not set_code:
                                logger.warning(f"Failed to get set code for variant: {set_code}")
                                continue

                            # Determine foil status and version
                            is_foil = parsed_card.get('Foil', False)
                            version = CardVersion.normalize(parsed_card.get('Version', 'Standard'))
                            if not version:
                                logger.warning(f"Failed to get version for variant: {parsed_card}")
                                continue
                            
                            card_info = {
                                'name': clean_name,
                                'set_name': set_name,
                                'set_code': set_code,
                                'quality': quality,
                                'language': language,
                                'price': price,
                                'quantity': quantity,
                                'foil': is_foil,
                                'version': version
                            }

                            # Deduplicate variants
                            variant_key = (
                                card_info['name'],
                                card_info['set_name'],
                                card_info['set_code'],
                                card_info['quality'],
                                card_info['language'],
                                card_info['foil'],
                                card_info['version']
                            )
                            if variant_key not in seen_variants:
                                cards.append(card_info)
                                seen_variants.add(variant_key)

                        except Exception as e:
                            logger.error(f"Error processing variant: {str(e)}", exc_info=True)
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
            
            # Add missing columns with default values and convert types
            for col, dtype in standard_columns.items():
                if col not in df.columns:
                    df[col] = dtype()
                df[col] = df[col].astype(dtype)
            
            return df
            
        except Exception as e:
            logger.error(f"Error creating DataFrame for {site.name}: {str(e)}", exc_info=True)
            return pd.DataFrame()
        
    def extract_info_hawk_json(self, json_data, site, card_names):
        """Extract card information from Hawk API response with deduplication"""
        if not json_data or 'Results' not in json_data:
            logger.warning(f"No valid results in Hawk response for {site.name}")
            return pd.DataFrame()
            
        cards = []
        processed_cards = set()  # Track unique card variants
        
        try:
            # Process each result
            for result in json_data['Results']:
                if not result.get('Document'):
                    continue
                    
                doc = result['Document']
                
                # Get basic card info
                card_name = doc.get('card name', [''])[0]
                if not card_name or card_name not in card_names:
                    continue
                    
                # Process child attributes (variants)
                child_attrs = doc.get('hawk_child_attributes_hits', [])
                for child_attr_group in child_attrs:
                    for item in child_attr_group.get('Items', []):
                        try:
                            # Extract condition and finish
                            option_condition = item.get('option_condition', ['NM'])[0]
                            option_finish = item.get('option_finish', ['Non-Foil'])[0]
                            
                            # Extract price and inventory
                            price = float(item.get('child_price_sort_bc', ['0.0'])[0])
                            inventory = int(item.get('child_inventory_level', ['0'])[0])
                            
                            if inventory <= 0:
                                continue

                            # Create unique identifier for deduplication
                            variant_key = (
                                card_name,
                                doc.get('set', [''])[0],
                                option_condition,
                                'Foil' in option_finish,
                                price
                            )
                            
                            # Skip if we've already processed this variant
                            if variant_key in processed_cards:
                                continue
                                
                            processed_cards.add(variant_key)
                                    
                            # Create card info dictionary
                            card_info = {
                                'name': card_name,
                                'set_name': doc.get('set', [''])[0],
                                'quality': option_condition,
                                'language': 'English',  # Default for F2F
                                'quantity': inventory,
                                'price': price,
                                'version': 'Standard',
                                'foil': 'Foil' in option_finish,
                                'set_code': doc.get('set_code', [''])[0]
                            }
                            
                            cards.append(card_info)
                            
                        except Exception as e:
                            logger.error(f"Error processing variant for {card_name} in {site.name}: {str(e)}", exc_info=True)
                            continue
                                
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
                'quantity': int,
                'set_code': str
            }
            
            # Add missing columns with default values
            for col, dtype in standard_columns.items():
                if col not in df.columns:
                    df[col] = dtype()
                df[col] = df[col].astype(dtype)
            
            # Normalize quality values
            df['quality'] = df['quality'].apply(CardQuality.normalize)
            
            # Remove any remaining duplicates
            df = df.drop_duplicates(subset=['name', 'set_name', 'quality', 'foil', 'price'])
            
            logger.info(f"Processed {len(df)} unique variants for {len(df['name'].unique())} distinct cards")
            
            return df
                
        except Exception as e:
            logger.error(f"Error processing Hawk JSON for {site.name}: {str(e)}", exc_info=True)
            return pd.DataFrame()
 
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
            logger.error(f"Error processing Shopify JSON for {site.name}: {str(e)}", exc_info=True)
            return pd.DataFrame()

    async def get_site_details(self, site, auth_required=True):
        auth_token = None
        search_url = site.url.rstrip('/')
        try:
            # Make initial request to get auth token
            initial_response = await self.network.fetch_url(search_url)
            if not initial_response or not initial_response.get("content"):
                logger.error(f"Initial request failed for {site.name}")
                return None
                
            logger.info(f"Initial request successful for {site.name}")

            response_content = initial_response["content"]

            # Parse response and get auth token
            soup = BeautifulSoup(response_content, "html.parser")
            if auth_required:
                auth_token = await self.network.get_auth_token(soup, site)
                
                if not auth_token:
                    logger.info(f"Failed to get auth token for {site.name}")
                    # Filter relevant headers for POST
                    
            site_details = initial_response.get("site_details")
            if isinstance(site_details, dict):
                headers = site_details.get("headers", {})
                # Filter relevant headers for POST
                relevant_headers = {
                    key: value
                    for key, value in headers.items()
                    if key.lower() in ['cache-control', 'content-type', 'accept-language', 'accept-encoding']
                }
            cookies = site_details.get("cookies", {})
            if isinstance(cookies, dict):
                cookie_str = "; ".join([f"{key}={value}" for key, value in cookies.items()])

            return auth_token, relevant_headers, cookie_str

        except Exception as e:
            logger.error(f"Error in crystal commerce search for {site.name}: {str(e)}", exc_info=True)
            return None

    async def search_crystalcommerce(self, site, card_names):
        """
        Simplified crystal commerce search with better error handling.
        """
        search_url = site.url.rstrip('/')
        try:
            
            auth_token, relevant_headers, cookie_str = await self.get_site_details(site)
            
            relevant_headers.update({
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Cookie": cookie_str,
            })

            # Prepare search payload
            clean_names = [clean_card_name(name, card_names) for name in card_names if name]
            if not clean_names:
                logger.error(f"No valid card names to search for {site.name}")
                return None
            
            query_string = "\r\n".join(clean_names)
            if "orchardcitygames" in site.name.lower():
                query_string = urllib.parse.quote_plus(query_string)
                # logger.info(f"Query string for {site.name}: {query_string}")
                
            payload = {
                "authenticity_token": auth_token,
                "query": query_string,
                "submit": "Continue"
            }
            
            response = await self.network.post_request(search_url, payload, headers=relevant_headers)
            if not response:
                logger.error(f"Search request failed for {site.name}")
                return None

            # Return response for further processing
            return BeautifulSoup(response, "html.parser")

        except Exception as e:
            logger.error(f"Error in crystal commerce search for {site.name}: {str(e)}", exc_info=True)
            return None
       
    
    async def search_hawk(self, site, card_names):
        """Submit individual card searches to Hawk API with proper name formatting"""
        try:
            results = []
            
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json, text/plain, */*',
                'Origin': 'https://www.facetofacegames.com',
                'Referer': 'https://www.facetofacegames.com/deck-results/',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                'Accept-Language': 'en-US,en;q=0.9',
                'Connection': 'keep-alive'
            }
            
            
            for card_name in card_names:
                
                api_url, json_payload = CardService.create_hawk_url_and_payload(site, card_name)
                # Debug logging
                logger.debug(f"Hawk API Request for {card_name}:")
                logger.debug(f"URL: {api_url}")
                logger.debug(f"Payload: {json_payload}")
                
                # Add delay between requests
                if results:  # Skip delay for first request
                    await asyncio.sleep(1.5)
                
                try:
                    async with self.network.session.post(
                        api_url,
                        data=json_payload,
                        headers=headers,
                        timeout=30
                    ) as response:
                        status = response.status
                        logger.debug(f"Response Status for {card_name}: {status}")
                        
                        if status == 400:
                            error_text = await response.text()
                            logger.debug(f"API Error Response for {card_name}:")
                            logger.debug(f"Status: {status}")
                            logger.debug(f"Error Details: {error_text[:1000]}")
                            continue
                            
                        response.raise_for_status()
                        response_text = await response.text()
                        
                        try:
                            card_results = json.loads(response_text)
                            if card_results and 'Results' in card_results:
                                results.extend(card_results['Results'])
                                logger.debug(f"Successfully processed {card_name} with {len(card_results['Results'])} results")
                            else:
                                logger.warning(f"No results for {card_name}, Response: {response_text[:200]}")
                        except json.JSONDecodeError as e:
                            logger.error(f"Invalid JSON response for {card_name}: {str(e)}", exc_info=True)
                            logger.error(f"Raw response: {response_text[:200]}")
                            continue
                            
                except Exception as e:
                    logger.error(f"Request failed for {card_name}: {str(e)}", exc_info=True)
                    continue
                    
            if results:
                logger.debug(f"Successfully processed {card_name} with {len(card_results['Results'])} results")          
                return {"Results": results}
                
            logger.error(f"No valid results from Hawk API for {site.name}")
            return None
                
        except Exception as e:
            logger.error(f"Error in Hawk search: {str(e)}", exc_info=True)
            return None
    

    async def search_shopify(self, site, card_names):
        """Get card data from Shopify via Binder API"""
        try:
            _, relevant_headers, cookie_str = await self.get_site_details(site, auth_required=False)
            api_url, json_payload = CardService.create_shopify_url_and_payload(site, card_names)
            relevant_headers.update({
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Cookie": cookie_str,
            })
        
            response = await self.network.post_request(api_url, json_payload, headers=relevant_headers)
            
            if not response:
                logger.error(f"Failed to get response from Binder API for {site.name}")
                return None
            
            try:
                return json.loads(response)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON response from {site.name}: {str(e)}", exc_info=True)
                return None
                
        except Exception as e:
            logger.error(f"Error searching Shopify site {site.name}: {str(e)}", exc_info=True)
            return None
    
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
            logger.error(f"Error parsing variant title '{title}': {str(e)}", exc_info=True)
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
        try:
            if not any([product_foil, product_version, variant_data]):
                return False
                
            check_strings = [
                s.lower() for s in [product_foil, product_version, variant_data]
                if s is not None
            ]
            
            return any('foil' in s for s in check_strings)
        except Exception as e:
            logger.exception(f"Error in detect_foil {str(e)}", exc_info=True)
            return None
    
    @staticmethod
    def extract_price(variant):
        """Modified to handle both dict and object card data"""
        try:
            price_elem = (
                variant.find("span", {"class": "regular price"}) or
                variant.find("span", {"class": "price"}) or
                variant.find("span", {"class": "variant-price"})
            )

            if not price_elem:
                logger.debug("No price element found in variant")
                return None
                
            price_text = price_elem.text.strip()
            
            # Remove currency symbols and normalize
            price_value = normalize_price(price_text)
            if not price_value or price_value < 0 :
                logger.debug(f"Price {price_value} is 0 or negative")
                return None
            return price_value
            
        except Exception as e:
            logger.error(f"Error extracting price: {str(e)}", exc_info=True)
            return None


    @staticmethod 
    def extract_quality_language(quality_language):
        """Extract and normalize quality and language from variant"""
        try:
            if not quality_language:
                return 'DMG', 'Unknown'  # Default values for empty input
                
            # Convert to string if list is passed
            if isinstance(quality_language, list):
                quality_language = ', '.join(str(x) for x in quality_language)
            elif not isinstance(quality_language, str):
                return 'DMG', 'Unknown'  # Default values for non-string input
                
            # Handle specific cases
            if "Website Exclusive" in quality_language:
                variant_parts = quality_language.split(',', 1)
                if len(variant_parts) > 1:
                    quality_language = variant_parts[1].strip()

            quality_parts = quality_language.split(',')
            if len(quality_parts) >= 2:
                raw_quality = quality_parts[0].strip()
                raw_language = quality_parts[1].strip()
            else:
                # If no comma found, assume quality is the whole string and language is English
                raw_quality = quality_language.strip()
                raw_language = 'Unknown'

            # Handle special cases
            if raw_language == 'SIGNED by artist':
                logger.info(f"Signed card found for variant {quality_language}")
                raw_language = 'Unknown'

            quality = CardQuality.normalize(raw_quality)
            language = CardLanguage.normalize(raw_language)
            
            return quality or 'DMG', language or 'Unknown'

        except Exception as e:
            logger.exception(f"Error in extract_quality_language with input '{quality_language}': {str(e)}", exc_info=True)
            return 'DMG', 'Unknown'  # Return default values on error

    @staticmethod
    def extract_quantity(variant):
        try:
            # Check for quantity in various formats
            qty_elem = (
                variant.find("span", {"class": "variant-short-info variant-qty"}) or
                variant.find("span", {"class": "variant-short-info"}) or
                variant.find("span", {"class": "variant-qty"}) or
                variant.find("input", {"class": "qty", "type": "number"})
            )
            
            if not qty_elem:
                # logger.info(f"No quantity element found in variant {variant}")
                return None
            
            # Convert to integer and validate
            try:
                # Handle different quantity formats
                if qty_elem.name == 'input':
                    # Check both max attribute and value
                    qty = qty_elem.get('max') or qty_elem.get('value')
                    quantity = int(qty) if qty else 0
                else:
                    # logger.info(f"Quantity element: {qty_elem}")
                    qty_text = qty_elem.text.strip()
                    # Extract numbers from text (e.g., "5 in stock" -> "5")
                    quantity = extract_numbers(qty_text)
                    # logger.info(f"Quantity text: {qty_text} -> {quantity}: {type(quantity)}")
                
                if quantity <= 0:
                    logger.info(f"Quantity {quantity} is negative...")
                    return None
                return quantity
            except (ValueError, TypeError):
                logger.info(f"Invalid quantity value: {qty}")
                return None
            
        except Exception as e:
            logger.exception(f"Error in extract_quantity {str(e)}", exc_info=True)
            return None
            
    @staticmethod
    def find_name_version_foil(place_holder):
        """Improved version/foil detection"""
        try:
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
        
        except Exception as e:
            logger.exception(f"Error in find_name_version_foil {str(e)}", exc_info=True)
            return None

    @staticmethod
    def log_cards_df_stat(site, cards_df):
        try:
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
        except Exception as e:
            logger.exception(f"Error in log_cards_df_stat {str(e)}", exc_info=True)
            return None
    
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

    @staticmethod
    def normalize_variant_description(variant_description):
        try:
            cleaned_description = variant_description.split(":")[-1].strip()
            variant_parts = cleaned_description.split(",")
            return [part.strip() for part in variant_parts]
        except Exception as e:
            logger.exception(f"Error in normalize_variant_description {str(e)}", exc_info=True)
            return None
        
    @staticmethod
    def is_magic_card(product):
        """Check if the product is a Magic card by inspecting href path"""
        try:
            # Look for the meta div which contains category and name
            meta_div = product.find("div", {"class": "meta"})
            if meta_div:
                # Find category link
                category_link = meta_div.find("a", href=True)
                if category_link:
                    href = category_link.get("href", "").lower()
                    if ("magic_singles" in href or 
                        "cartes_individuelles_magic" in href or
                        "magic_the_gathering_singles" in href or
                        "unfinity" in href or
                        "commander_fallout" in href):
                        return True
            return False
        except Exception as e:
            logger.error(f"Error checking if product is Magic card: {str(e)}", exc_info=True)
            return False
