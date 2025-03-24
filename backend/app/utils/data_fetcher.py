import asyncio
import json
import logging
import re
import time
import urllib
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

import pandas as pd
from app.constants import CardQuality, CardVersion
from app.extensions import db
from app.services import CardService
from app.services import SiteService
from app.utils.helpers import (
    clean_card_name,
    detect_foil,
    extract_numbers,
    extract_price,
    extract_quantity,
    extract_quality_language,
    find_name_version_foil,
    normalize_variant_description,
    normalize_price,
    parse_card_string,
)
from app.utils.selenium_driver import MethodRateLimiter, network
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


# Statistic bucket structure to collect site results summary:
class SiteScrapeStats:
    def __init__(self):
        self.site_stats = {}

    def record_site(self, site_name, search_time, extract_time, total_time, found_cards, total_cards, total_variants):
        self.site_stats[site_name] = {
            "search_time": search_time,
            "extract_time": extract_time,
            "total_time": total_time,
            "found_cards": found_cards,
            "total_cards": total_cards,
            "total_variants": total_variants,
        }

    def log_summary(self):
        logger.info("=" * 95)
        logger.info(
            f"{'Site':<25} {'# Found':<8} {'Total Cards':<12} {'Variants':<9} {'Search(s)':<10} {'Extract(s)':<11} {'Total(s)':<9}"
        )
        logger.info("-" * 95)

        for site, stats in sorted(self.site_stats.items(), key=lambda item: item[1]["found_cards"], reverse=True):
            try:
                found_cards = stats.get("found_cards", 0)
                total_cards = stats.get("total_cards", 0)
                total_variants = stats.get("total_variants", 0)
                search_time = stats.get("search_time", 0.0)
                extract_time = stats.get("extract_time", 0.0)
                total_time = stats.get("total_time", 0.0)

                logger.info(
                    f"{site:<25} {found_cards:<8} {total_cards:<12} {total_variants:<9} "
                    f"{search_time:<10.2f} {extract_time:<11.2f} {total_time:<9.2f}"
                )
            except KeyError as e:
                logger.error(f"Missing key {e} in site stats for {site}")

        logger.info("=" * 95 + "\n")


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
    SCRAPPING_METHOD_F2F = 3
    SCRAPPING_METHOD_SHOPIFY = 4
    SCRAPPING_METHOD_OTHER = 5
    scrapping_method_dict = {
        "crystal": SCRAPPING_METHOD_CRYSTAL,
        "scrapper": SCRAPPING_METHOD_SCRAPPER,
        "f2f": SCRAPPING_METHOD_F2F,
        "shopify": SCRAPPING_METHOD_SHOPIFY,
        "other": SCRAPPING_METHOD_OTHER,
    }

    def __init__(self):
        self.error_collector = ErrorCollector.get_instance()
        self.error_collector.reset()
        # Create a thread pool for CPU-intensive operations
        self.thread_pool = ThreadPoolExecutor(max_workers=8)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Clean up thread pool resources
        try:
            self.thread_pool.shutdown(wait=True)
            logger.debug("Thread pool shutdown complete")
        except Exception as e:
            logger.error(f"Error shutting down thread pool: {str(e)}")

    async def detect_response_type(self, response_text):
        """Detect response type and format"""
        if not response_text:
            return None, None

        # Check if it's JSON (Shopify API response)
        try:
            json_data = json.loads(response_text)
            if isinstance(json_data, list) and json_data and "searchName" in json_data[0]:
                return "shopify_json", json_data
        except json.JSONDecodeError:
            pass

        # Check if it's HTML
        if any(marker in response_text for marker in ["<!DOCTYPE html>", "<html", "<?xml"]):
            # Check for loading indicators
            loading_indicators = [
                "Searching... Please wait",
                "custom-loader",
                "savedLoader",
                "loading-overlay",
                "spinner",
            ]
            is_loading = any(indicator in response_text for indicator in loading_indicators)
            return "html", {"is_loading": is_loading}

        return "unknown", None

    async def scrape_multiple_sites(self, sites, card_names):
        """Enhanced scraping with proper Selenium integration"""
        scrape_stats = SiteScrapeStats()
        try:
            start_time = time.time()  # Start timing
            results = []

            # Group sites by their scraping method
            sites_by_method = defaultdict(list)
            for site in sites:
                sites_by_method[site.method].append(site)

            # Pre-warm site_details_cache concurrently
            prewarm_tasks = [SiteService.init_site_details_cache(site) for site in sites]
            prewarm_results = await asyncio.gather(*prewarm_tasks)
            logger.info(
                f"Pre-warmed cache for {len([r for r in prewarm_results if r is not None])}/{len(sites)} sites."
            )

            logger.info(f"Processing {len(sites)} sites, grouped by scraping method.")

            async def process_group(method, method_sites):
                """Process a group of sites sharing the same method."""
                limiter = MethodRateLimiter()
                concurrency = limiter.get_concurrency(method)
                rate_limit = limiter.get_rate_limit(method)

                logger.info(
                    f"Processing {len(method_sites)} sites with method '{method}' "
                    f"using concurrency {concurrency} and rate limit {rate_limit}/sec"
                )

                semaphore = asyncio.Semaphore(concurrency)

                async def process_with_limit(site):
                    async with semaphore:
                        try:
                            return await self.process_site(site, card_names, scrape_stats)
                        except Exception as e:
                            logger.error(f"Error processing {site.name}: {str(e)}", exc_info=True)
                            return None

                # Run all sites for this method concurrently
                scraped_data = await asyncio.gather(
                    *[process_with_limit(site) for site in method_sites],
                    return_exceptions=True,
                )

                # Collect valid results
                for result in scraped_data:
                    if isinstance(result, list):  # Ensure it's a valid list of results
                        results.extend(result)

                    # Process each method's sites concurrently

            await asyncio.gather(
                *[process_group(method, method_sites) for method, method_sites in sites_by_method.items()]
            )

            elapsed_time = round(time.time() - start_time, 2)
            logger.info(
                f"Completed scraping {len(sites)} sites with {len(results)} total results in {elapsed_time} seconds"
            )

            scrape_stats.log_summary()
            return results

        except Exception as e:
            logger.error(f"Fatal error in scrape_multiple_sites: {str(e)}", exc_info=True)
            raise

    async def process_site(self, site, card_names, scrape_stats: SiteScrapeStats):
        """Process a single site and return results without saving to DB"""
        start_time = time.time()  # Start timing
        elapsed_time_search = 0
        elapsed_time_extract = 0
        scrapping_method = ExternalDataSynchronizer.scrapping_method_dict.get(
            site.method.lower(), ExternalDataSynchronizer.SCRAPPING_METHOD_CRYSTAL
        )

        logger.info(f"Processing site: {site.name}")
        logger.info(f"\t o Strategy: {site.method}")
        logger.info(f"\t o URL: {site.url}")
        if site.api_url:
            logger.info(f"\t o API URL: {site.api_url}")

        try:
            if scrapping_method == ExternalDataSynchronizer.SCRAPPING_METHOD_SHOPIFY:
                # Get data from Shopify API
                start_time_search = time.time()  # Start timing
                json_data = await self.search_shopify(site, card_names)
                elapsed_time_search = round(time.time() - start_time_search, 2)  # Compute elapsed time

                if not json_data:
                    self.error_collector.unreachable_stores.add(site.name)
                    self.log_site_error(
                        site.name,
                        "Connection Error",
                        "Failed to retrieve data from Shopify API.",
                    )
                    return None

                start_time_extract = time.time()  # Start timing
                cards_df = await self.extract_info_shopify_json(json_data, site, card_names)
                elapsed_time_extract = round(time.time() - start_time_extract, 2)  # Compute elapsed time

            elif scrapping_method == ExternalDataSynchronizer.SCRAPPING_METHOD_F2F:

                start_time_search = time.time()  # Start timing
                json_data = await self.search_f2f(site, card_names)
                elapsed_time_search = round(time.time() - start_time_search, 2)  # Compute elapsed time

                if not json_data:
                    self.error_collector.unreachable_stores.add(site.name)
                    self.log_site_error(
                        site.name,
                        "Connection Error",
                        "Failed to retrieve data from f2f API.",
                    )
                    return None

                start_time_extract = time.time()  # Start timing
                cards_df = await self.extract_info_f2f_json(json_data, site, card_names)
                elapsed_time_extract = round(time.time() - start_time_extract, 2)  # Compute elapsed time

            else:
                start_time_search = time.time()  # Start timing
                soup = await self.search_crystalcommerce(site, card_names)
                elapsed_time_search = round(time.time() - start_time_search, 2)  # Compute elapsed time

                if not soup:
                    self.error_collector.unreachable_stores.add(site.name)
                    self.log_site_error(
                        site.name,
                        "Connection Error",
                        "Failed to retrieve data from site. Site may be down or blocking requests.",
                    )
                    return None

                start_time_extract = time.time()  # Start timing
                cards_df = await self.extract_info_crystal(soup, site, card_names, scrapping_method)
                elapsed_time_extract = round(time.time() - start_time_extract, 2)  # Compute elapsed time

                if cards_df.empty:
                    old_strategy = scrapping_method
                    scrapping_method = (
                        ExternalDataSynchronizer.SCRAPPING_METHOD_SCRAPPER
                        if scrapping_method == ExternalDataSynchronizer.SCRAPPING_METHOD_CRYSTAL
                        else ExternalDataSynchronizer.SCRAPPING_METHOD_CRYSTAL
                    )
                    logger.info(f"Strategy {old_strategy} failed, attempting with {scrapping_method}")

                    start_time_extract = time.time()  # Start timing
                    cards_df = await self.extract_info_crystal(soup, site, card_names, scrapping_method)
                    elapsed_time_extract = round(time.time() - start_time_extract, 2)  # Compute elapsed time

            if cards_df is None or cards_df.empty:
                self.log_site_error(
                    site.name,
                    "No Data Found",
                    f"Strategy '{site.method}' failed to extract any valid card data",
                )
                return None

            if cards_df is not None and not cards_df.empty:
                # Create summary of results
                # self.log_cards_df_stat(site, cards_df)
                total_cards = len(card_names)
                found_cards = cards_df["name"].nunique()
                elapsed_time = round(time.time() - start_time, 2)  # Compute elapsed time

                logger.info(
                    f"Successfully processed {site.name} [{site.method}] found {found_cards} / {total_cards} ({len(cards_df)} total variants)"
                )

                # Instead of logging right here, record into scrape_stats:
                scrape_stats.record_site(
                    site.name,
                    elapsed_time_search,
                    elapsed_time_extract,
                    elapsed_time,
                    found_cards,
                    total_cards,
                    len(cards_df),
                )

                # if found_cards < total_cards:
                #     missing_cards = set(card_names) - set(cards_df['name'].unique())
                #     #logger.warning(f"Missing cards for {site.name}: {', '.join(missing_cards)}")
                #     logger.warning(f"Missing cards {len(missing_cards)} for {site.name}")

                # Convert DataFrame rows to results
                results = (
                    cards_df.rename(columns={"clean_name": "name"})  # Only if necessary, ensure correct column mapping
                    .assign(
                        price=lambda df: df["price"].fillna(0.0).astype(float),
                        quantity=lambda df: df["quantity"].fillna(0).astype(int),
                        foil=lambda df: df["foil"].fillna(False).astype(bool),
                        version=lambda df: df["version"].fillna("Standard"),
                    )[
                        [
                            "name",
                            "set_name",
                            "set_code",
                            "quality",
                            "language",
                            "price",
                            "quantity",
                            "foil",
                            "version",
                            "variant_id",
                        ]
                    ]
                    .to_dict(orient="records")
                )
                for r in results:
                    r["site_id"] = site.id
                    r["site_name"] = site.name
                return results
            else:
                logger.warning(f"No valid cards found for {site.name}")
                return None

        except Exception as e:
            elapsed_time = round(time.time() - start_time, 2)
            self.log_site_error(site.name, f"Processing Error (after {elapsed_time} seconds)", str(e))
            return None

    async def process_dataframe(self, func, *args, **kwargs):
        """Run DataFrame operations in thread pool to avoid blocking the event loop"""
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(self.thread_pool, lambda: func(*args, **kwargs))
        except Exception as e:
            logger.error(f"Error in thread pool execution: {str(e)}")
            return pd.DataFrame()

    async def extract_info_crystal(self, soup, site, card_names, scrapping_method):
        """Extract card information with non-blocking execution"""

        # Run the CPU-intensive operations in a thread pool
        # return await self.process_dataframe(
        #     self._extract_info_crystal_sync_vectorized, soup, site, card_names, scrapping_method
        # )
        return await self.process_dataframe(self._extract_info_crystal_sync, soup, site, card_names, scrapping_method)

    def _extract_info_crystal_sync(self, soup, site, card_names, scrapping_method):
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
            "oversized cards",
            "promos: miscellaneous",
            "prerelease cards",
            "brawl",
        }
        promo_set_mappings = {
            "CBL Bundle Promo": "Commander Legends: Battle for Baldur's Gate",
            "Treasure Chest Promo": "ixalan promos",
            "Bundle Promo": "Promo Pack",  # Generic bundle promos
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
                    required_attrs = [
                        "data-name",
                        "data-price",
                        "data-category",
                        "data-variant",
                    ]
                    if not all(attr in data for attr in required_attrs):
                        continue

                    current_card = parse_card_string(data["data-name"])
                    if not current_card:
                        continue

                    # Clean and validate card name
                    name = clean_card_name(current_card["Name"], card_names)
                    # logger.info(f"after clean_card_name form: {name} ")
                    if not name or (name not in card_names and name.split(" // ")[0].strip() not in card_names):
                        continue

                    category = data.get("data-category")
                    set_name = category
                    # logger.info(f"after data.get('data-category') form: {set_name} ")

                    if any(test in category.lower() for test in excluded_categories):
                        if category == "Brawl":
                            product_link = form.find_previous("a", itemprop="url")
                            # logger.info(f"product_link: {product_link} for site: {site.name}\n {category}")

                            if product_link:
                                product_url = product_link.get("href")
                                set_name = CardService.extract_magic_set_from_href(product_url)
                                # logger.info(f"product_url: {product_url} for site: {site.name}\n {set_name}")
                        elif category == "Promos: Miscellaneous":
                            card_name = data.get("data-name", "")
                            name_parts = card_name.split(" - ")
                            promo_suffix = name_parts[-1] if len(name_parts) > 1 else None
                            if promo_suffix and promo_suffix in promo_set_mappings:
                                set_name = promo_set_mappings[promo_suffix]

                        continue

                    # Try to match with closest set name using CardService
                    set_name = CardService.get_closest_set_name(set_name)

                    if not set_name or set_name.lower() == "unknown":
                        original_set_name = set_name
                        # Fallback to extracting from URL (new logic)
                        product_link = form.find_previous("a", itemprop="url")
                        if product_link:
                            product_url = product_link.get("href", "")
                            fallback_set = CardService.extract_magic_set_from_href(product_url)
                            if fallback_set:
                                set_name = fallback_set
                                logger.info(
                                    f"[SET CODE] Fallback used for set '{original_set_name}' -> '{set_name}' using URL: {product_url}"
                                )
                            else:
                                logger.warning(
                                    f"[SET CODE] No valid fallback set found in URL for '{original_set_name}': {product_url}"
                                )
                                continue  # Skip if still no valid set found
                        else:
                            logger.warning(f"No product URL found for '{original_set_name}'")
                            continue  # Skip if no URL found

                    # logger.info(f"after get_closest_set_name form: {set_name} ")
                    set_code = CardService.get_clean_set_code_from_set_name(set_name)
                    if not set_code:
                        # Attempt fallback using parts of data-name
                        name_parts = data.get("data-name", "").split(" - ")
                        for part in reversed(name_parts):  # Start from the most specific suffix
                            fallback_set_name = CardService.get_closest_set_name(part.strip())
                            fallback_set_code = CardService.get_clean_set_code_from_set_name(fallback_set_name)
                            if fallback_set_code:
                                logger.debug(
                                    f"Fallback set code found from data-name part '{part}': {fallback_set_name} ({fallback_set_code})"
                                )
                                set_code = fallback_set_code
                                set_name = fallback_set_name
                                break
                        if not set_code:
                            logger.info(
                                f"[SET CODE] Skipping card after fallback {name} unknown set: {set_code} for site: {site.name}\n {data}"
                            )
                            continue
                    if set_code.lower() == "pbook":
                        logger.info(
                            f"after pbook: {set_code} name:{set_name} for site: {site.name}\n data: {data}\n {data}"
                        )
                        continue
                    # logger.info(f"after get_clean_set_code form: {set_code} ")

                    test = data.get("data-variant", "").strip()
                    if not test:
                        continue

                    quality, language = extract_quality_language(test)
                    # logger.info(f"after extract_quality_language form: {quality} ")

                    # Parse name, version, and foil status
                    unclean_name, version, foil = find_name_version_foil(data["data-name"])
                    is_foil = detect_foil(product_foil=foil, product_version=version, variant_data=test)
                    version = CardVersion.normalize(version or "Standard")

                    # Extract and validate quantity
                    quantity = extract_quantity(form)
                    if not quantity or quantity <= 0:
                        quantity = 1

                    variant_id = data.get("data-vid")
                    if not variant_id:
                        continue
                    # Create card info dictionary
                    card_info = {
                        "name": name,
                        "set_name": set_name,
                        "set_code": set_code,
                        "version": version,
                        "language": language,
                        "foil": is_foil,
                        "quality": quality,
                        "quantity": quantity,
                        "price": normalize_price(data["data-price"]),
                        "variant_id": variant_id,
                    }

                    # Create variant key for deduplication
                    variant_key = (
                        card_info["name"],
                        card_info["set_name"],
                        card_info["set_code"],
                        card_info["version"],
                        card_info["language"],
                        card_info["foil"],
                        card_info["quality"],
                        card_info["price"],
                    )

                    if variant_key not in seen_variants:
                        cards.append(card_info)
                        seen_variants.add(variant_key)

                except Exception as e:
                    logger.error(f"Error processing form in {site.name}: {str(e)}", exc_info=True)
                    continue

        else:
            # Original scrapper strategy with enhanced validation
            content = soup.find(
                "div",
                {"class": ["content", "content clearfix", "content inner clearfix"]},
            )
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
                                "span",
                                {"class": "variant-short-info variant-description"},
                            ) or variant.find("span", {"class": "variant-short-info"})

                            if not variant_data:
                                continue
                            form_tag = variant.find("form", {"class": "add-to-cart-form"})
                            if not form_tag:
                                continue
                            variant_id = form_tag.get("data-vid")
                            if not variant_id:
                                logger.warning(f"variant_id not found for variant")
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

                            clean_name = clean_card_name(parsed_card.get("Name", name_header.text), card_names)
                            if not clean_name or (
                                clean_name not in card_names and clean_name.split(" // ")[0].strip() not in card_names
                            ):
                                logger.debug(f"Invalid card name: {clean_name}")
                                continue

                            # Extract and validate quality and language
                            quality_language = normalize_variant_description(variant_data.text)
                            # logger.info(f"after normalize_variant_description: {quality_language}")
                            quality, language = extract_quality_language(quality_language)

                            if not quality or not language:
                                logger.warning(f"Quality or language not found for variant{quality_language}")
                                continue

                            # Extract and validate quantity
                            quantity = extract_quantity(variant)
                            if quantity is None or quantity <= 0:
                                logger.warning(f"Invalid quantity for variant: {quantity}")
                                continue

                            # Extract and validate price
                            price = extract_price(variant)
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
                            set_code = CardService.get_clean_set_code_from_set_name(set_name)
                            if not set_code:
                                # Attempt fallback using parts of data-name
                                name_parts = name_header.split(" - ")
                                for part in reversed(name_parts):  # Start from the most specific suffix
                                    fallback_set_name = CardService.get_closest_set_name(part.strip())
                                    fallback_set_code = CardService.get_clean_set_code_from_set_name(fallback_set_name)
                                    if fallback_set_code:
                                        logger.debug(
                                            f"Fallback set code found from data-name part '{part}': {fallback_set_name} ({fallback_set_code})"
                                        )
                                        set_code = fallback_set_code
                                        set_name = fallback_set_name
                                        break
                                if not set_code:
                                    logger.warning(
                                        f"[SET CODE] Failed to get set code for variant set name: {set_name}"
                                    )
                                    continue

                            # Determine foil status and version
                            is_foil = parsed_card.get("Foil", False)
                            version = CardVersion.normalize(parsed_card.get("Version", "Standard"))
                            if not version:
                                logger.warning(f"Failed to get version for variant: {parsed_card}")
                                continue

                            card_info = {
                                "name": clean_name,
                                "set_name": set_name,
                                "set_code": set_code,
                                "language": language,
                                "version": version,
                                "foil": is_foil,
                                "quality": quality,
                                "quantity": quantity,
                                "price": price,
                                "variant_id": variant_id,
                            }

                            # Deduplicate variants
                            variant_key = (
                                card_info["name"],
                                card_info["set_name"],
                                card_info["set_code"],
                                card_info["language"],
                                card_info["version"],
                                card_info["foil"],
                                card_info["quality"],
                                card_info["price"],
                                card_info["variant_id"],
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

            df = self.standardize_card_dataframe(cards)
            logger.debug(f"[CRYSTAL] Processed {len(df)} unique variants for {len(df['name'].unique())} distinct cards")
            return df

        except Exception as e:
            logger.error(f"Error creating DataFrame for {site.name}: {str(e)}", exc_info=True)
            return pd.DataFrame()

    async def extract_info_f2f_json(self, json_data, site, card_names):
        """Extract card information from f2f API response with non-blocking execution"""
        return await self.process_dataframe(self._extract_info_f2f_json_sync, json_data, site, card_names)

    def _extract_info_f2f_json_sync(self, json_data, site, card_names):
        """Extract card information from F2F Shopify API response."""
        if not json_data or "Cards" not in json_data:
            logger.warning(f"No results in F2F response for {site.name}")
            return pd.DataFrame()

        cards = []
        processed_variants = set()

        try:
            for card_name, products in json_data["Cards"].items():
                if card_name not in card_names:
                    continue

                for product in products:
                    product_source = product["_source"]
                    set_name = product_source.get("MTG_Set_Name")
                    variants = product_source.get("variants", [])

                    for variant in variants:
                        inventory = variant.get("inventoryQuantity", 0)
                        if inventory <= 0:
                            continue

                        price = float(variant.get("price", 0))
                        condition = variant.get("selectedOptions", [{}])[0].get("value", "NM")
                        foil = "Foil" in product_source.get("MTG_Foil_Option", "")
                        set_code = CardService.get_clean_set_code_from_set_name(set_name)

                        variant_key = (card_name, set_name, condition, foil, price)
                        if variant_key in processed_variants:
                            continue
                        processed_variants.add(variant_key)
                        variant_id = variant["id"].split("/")[-1]
                        card_info = {
                            "name": card_name,
                            "set_name": set_name,
                            "set_code": set_code,
                            "language": product_source.get("General_Card_Language", "English"),
                            "version": "Standard",
                            "foil": foil,
                            "quality": CardQuality.normalize(condition),
                            "quantity": inventory,
                            "price": price,
                            "variant_id": variant_id,
                        }
                        cards.append(card_info)

            if not cards:
                logger.warning(f"No valid cards found in F2F response for {site.name}")
                return pd.DataFrame()

            df = self.standardize_card_dataframe(cards)
            logger.info(f"[F2F] Processed {len(df)} unique variants for {len(df['name'].unique())} distinct cards.")
            return df

        except Exception as e:
            logger.error(f"Error processing F2F JSON for {site.name}: {str(e)}", exc_info=True)
            return pd.DataFrame()

    async def extract_info_shopify_json(self, json_data, site, card_names):
        """Extract card information from Shopify API response with non-blocking execution"""
        return await self.process_dataframe(self._extract_info_shopify_json_sync, json_data, site, card_names)

    def _extract_info_shopify_json_sync(self, json_data, site, card_names):
        """Extract card information from Shopify API response"""
        cards = []

        try:
            for result in json_data:
                searched_card = result.get("searchName")
                if not searched_card or searched_card not in card_names:
                    continue

                products = result.get("products", [])
                for product in products:
                    # Basic product info
                    name = product.get("name")
                    set_name = product.get("setName")
                    collector_number = product.get("collectorNumber")

                    # Process variants
                    variants = product.get("variants", [])
                    for variant in variants:
                        # Skip if no quantity available
                        quantity = variant.get("quantity", 0)
                        if quantity <= 0:
                            continue

                        # Get variant details
                        title = variant.get("title", "").lower()
                        price = float(variant.get("price", 0.0))
                        variant_id = variant.get("shopifyId")

                        # Determine foil status
                        is_foil = "foil" in title

                        # Extract quality
                        extracted_quality = "Near Mint"  # Default
                        if "near mint" in title or "nm" in title:
                            extracted_quality = "Near Mint"
                        elif "lightly played" in title or "lp" in title:
                            extracted_quality = "Lightly Played"
                        elif "moderately played" in title or "mp" in title:
                            extracted_quality = "Moderately Played"
                        elif "heavily played" in title or "hp" in title:
                            extracted_quality = "Heavily Played"
                        elif "damaged" in title or "dmg" in title:
                            extracted_quality = "Damaged"
                        # TODO quality = CardQuality.normalize(quality)
                        quality = CardQuality.normalize(extracted_quality)

                        set_code = product.get("setCode", "")
                        if not set_code or set_code == "":
                            test_code = CardService.get_clean_set_code_from_set_name(set_name)
                            if not test_code:
                                logger.warning(
                                    f"[SET CODE] [SHOPIFY] Skipping card {name} unknown set: {test_code} for site: {site.name}"
                                )
                                continue
                            logger.debug(f"[SHOPIFY] set_code was empty for {name} setting to -> {test_code}")
                            set_code = test_code

                        card_info = {
                            "name": name,
                            "set_name": set_name,
                            "set_code": set_code,
                            "language": "English",  # Default for Shopify stores
                            "version": "Standard",
                            "foil": is_foil,
                            "quality": quality,
                            "quantity": quantity,
                            "price": price,
                            "variant_id": variant_id,
                            # "collector_number": collector_number,
                        }
                        cards.append(card_info)

            if not cards:
                logger.warning(f"No valid cards found in Shopify response for {site.name}")
                return pd.DataFrame()

            # df = pd.DataFrame(cards)

            # # Ensure standard column names and data types
            # standard_columns = {
            #     "name": str,
            #     "set_name": str,
            #     "set_code": str,
            #     "price": float,
            #     "version": str,
            #     "foil": bool,
            #     "quality": str,
            #     "language": str,
            #     "quantity": int,
            # }

            # # Add missing columns with default values
            # for col, dtype in standard_columns.items():
            #     if col not in df.columns:
            #         df[col] = dtype()
            #     df[col] = df[col].astype(dtype)

            # # Normalize quality and language values
            # df["quality"] = df["quality"].apply(CardQuality.normalize)
            # df["language"] = df["language"].apply(CardLanguage.normalize)

            df = self.standardize_card_dataframe(cards)
            logger.info(f"[SHOPIFY] Processed {len(df)} unique variants for {len(df['name'].unique())} distinct cards")
            return df
        except Exception as e:
            logger.error(
                f"Error processing Shopify JSON for {site.name}: {str(e)}",
                exc_info=True,
            )
            return pd.DataFrame()

    # async def get_site_details(self, site, auth_required=True):
    #     if site.name in self.site_details_cache:
    #         logger.info(f"Using cached site details for {site.name}")
    #         return self.site_details_cache[site.name]
    #     auth_token = None
    #     search_url = site.url.rstrip("/")
    #     try:
    #         # Make initial request to get auth token
    #         initial_response = await NetworkDriver.fetch_url(search_url)
    #         if not initial_response or not initial_response.get("content"):
    #             logger.error(f"Initial request failed for {site.name}")
    #             return None

    #         logger.info(f"Initial request successful for {site.name}")

    #         response_content = initial_response["content"]

    #         # Parse response and get auth token
    #         soup = BeautifulSoup(response_content, "html.parser")
    #         if auth_required:
    #             auth_token = await NetworkDriver.get_auth_token(soup, site)

    #             if not auth_token:
    #                 logger.info(f"Failed to get auth token for {site.name}")
    #                 # Filter relevant headers for POST

    #         site_details = initial_response.get("site_details")
    #         if isinstance(site_details, dict):
    #             headers = site_details.get("headers", {})
    #             # Filter relevant headers for POST
    #             relevant_headers = {
    #                 key: value
    #                 for key, value in headers.items()
    #                 if key.lower()
    #                 in [
    #                     "cache-control",
    #                     "content-type",
    #                     "accept-language",
    #                     "accept-encoding",
    #                 ]
    #             }
    #         cookies = site_details.get("cookies", {})
    #         if isinstance(cookies, dict):
    #             cookie_str = "; ".join([f"{key}={value}" for key, value in cookies.items()])

    #         self.site_details_cache[site.name] = (
    #             auth_token,
    #             relevant_headers,
    #             cookie_str,
    #         )
    #         return auth_token, relevant_headers, cookie_str

    #     except Exception as e:
    #         logger.error(
    #             f"Error in crystal commerce search for {site.name}: {str(e)}",
    #             exc_info=True,
    #         )
    #         return None

    async def generate_search_payload_crystal(self, site, card_names):
        """Generate search payload for CrystalCommerce sites."""
        auth_token, relevant_headers = await SiteService.get_site_details(site)

        query_string = "\r\n".join(card_names)
        if "orchardcitygames" in site.name.lower():
            query_string = urllib.parse.quote_plus(query_string)

        payload = {
            "authenticity_token": auth_token,
            "query": query_string,
            "submit": "Continue",
        }

        request_headers = dict(relevant_headers)
        request_headers.update(
            {
                "Connection": "keep-alive",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "Accept-Encoding": "gzip, deflate, br",
                "sec-ch-ua": '"Google Chrome";v="131", "Not;A=Brand";v="99"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
            }
        )
        return payload, request_headers

    async def _search_crystal_batch(self, site, batch_card_names):
        """
        Simplified crystal commerce search with better error handling.
        """
        max_retries = 3
        retry_count = 0
        backoff_factor = 1
        # Get site details including authentication token and headers
        search_url = site.url.rstrip("/")

        while retry_count < max_retries:
            try:
                retry_count += 1
                logger.debug(f"Attempting batch search for {site.name} (attempt {retry_count}/{max_retries})")

                payload, request_headers = await self.generate_search_payload_crystal(site, batch_card_names)

                # Make the request with an increased timeout
                response = await network.post_request(search_url, payload, headers=request_headers, site=site)

                if not response:
                    logger.warning(f"Search request failed for {site.name} (attempt {retry_count}/{max_retries})")
                    await asyncio.sleep(backoff_factor * (2 ** (retry_count - 1)))
                    continue

                logger.debug(f"Successfully received response for batch from {site.name}")

                # Process the response to handle potential "Connection closed" issues
                try:
                    soup = BeautifulSoup(response, "html.parser")

                    # Check if we got a valid response by looking for product elements
                    products = soup.find_all(["li", "div"], {"class": ["product", "products-container"]})

                    if not products:
                        logger.warning(f"No product elements found in response from {site.name}")

                        # Try to extract any errors from the response
                        error_elements = soup.find_all(["div", "p"], {"class": ["error", "alert", "notice"]})
                        if error_elements:
                            for error in error_elements:
                                logger.warning(f"Error from {site.name}: {error.text.strip()}")

                        # Continue with what we have anyway
                        pass

                    await asyncio.sleep(1.5)  # Add delay to avoid rate limiting
                    return soup

                except Exception as e:
                    logger.error(f"Error parsing response from {site.name}: {str(e)}")
                    await asyncio.sleep(backoff_factor * (2 ** (retry_count - 1)))
                    continue

            except Exception as e:
                logger.error(
                    f"Error in crystal commerce search for {site.name} (attempt {retry_count}/{max_retries}): {str(e)}",
                    exc_info=True,
                )
                await asyncio.sleep(backoff_factor * (2 ** (retry_count - 1)))
                continue

            backoff_factor *= 2

        logger.error(f"All {max_retries} attempts failed for batch search on {site.name}")
        return None

    async def search_crystalcommerce(self, site, card_names):
        """Search CrystalCommerce with batched requests for efficiency."""

        BATCH_SIZE = 40  # Number of cards per request

        try:

            # Prepare search payload
            clean_names = [clean_card_name(name, card_names) for name in card_names if name]

            if not clean_names:
                logger.error(f"No valid card names to search for {site.name}")
                return None

            # Split the card list into chunks of BATCH_SIZE
            card_batches = [clean_names[i : i + BATCH_SIZE] for i in range(0, len(clean_names), BATCH_SIZE)]

            # Prepare tasks for all batches
            tasks = [self._search_crystal_batch(site, batch) for batch in card_batches]

            logger.info(f"Sending {len(card_batches)} batch requests for {site.name}...")

            # Execute all batch requests concurrently
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Filter out exceptions and failed requests
            valid_results = []
            for i, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Batch {i+1} failed with exception: {str(result)}")
                    continue
                if result is None:
                    logger.warning(f"Batch {i+1} returned None")
                    continue
                valid_results.append(result)

            if not valid_results:
                logger.error(f"All batches failed for {site.name}")
                return None

            logger.info(f"Successfully processed {len(valid_results)}/{len(card_batches)} batches for {site.name}")

            # Combine all soups into a single soup object (simple merge)
            combined_html = "<html><body>" + "".join([str(soup) for soup in valid_results]) + "</body></html>"
            combined_soup = BeautifulSoup(combined_html, "html.parser")

            return combined_soup

        except Exception as e:
            logger.error(
                f"Error in search_crystalcommerce for {site.name}: {str(e)}",
                exc_info=True,
            )
            return None

    async def search_f2f(self, site, card_names):
        """Submit search in smaller batches to handle large result sets."""
        _, headers = await SiteService.get_site_details(site)

        # Break into batches of 20 cards each
        batch_size = 10
        batches = [card_names[i : i + batch_size] for i in range(0, len(card_names), batch_size)]
        logger.info(f"[F2F] Processing {len(card_names)} cards in {len(batches)} batches of {batch_size}")

        # Container for all results
        all_results = {"Cards": {}}

        # Process each batch
        for batch_index, batch_cards in enumerate(batches):
            normalized_card_names = [name.strip() for name in batch_cards]

            # Prepare payload for this batch
            batch_payload = {
                "sort": False,
                "filters": [
                    {"field": "Card Name", "values": normalized_card_names},
                    {"field": "in_stock", "values": ["1"]},
                ],
            }

            logger.info(
                f"[F2F] Processing batch {batch_index+1}/{len(batches)} with {len(normalized_card_names)} cards"
            )

            # Make the request
            response_text = await network.post_request(
                site.api_url, batch_payload, headers=headers, site=site, use_json=True
            )

            if response_text is None:
                logger.warning(f"[F2F] No response for batch {batch_index+1}")
                continue

            try:
                batch_results = json.loads(response_text)
                batch_cards_found = batch_results.get("Cards", {})
                batch_card_count = len(batch_cards_found)

                # Log batch results
                logger.info(f"[F2F] Batch {batch_index+1} found {batch_card_count} cards")

                if batch_card_count > 0:
                    # Log first few found cards for debugging
                    found_cards = list(batch_cards_found.keys())
                    logger.info(f"[F2F] Batch {batch_index+1} cards: {', '.join(found_cards[:5])}")

                    # Merge with overall results
                    all_results["Cards"].update(batch_cards_found)
                else:
                    # If no cards found, retry once with delay
                    logger.info(f"[F2F] No cards in batch {batch_index+1}, retrying after delay")
                    await asyncio.sleep(3)

                    retry_response = await network.post_request(
                        site.api_url, batch_payload, headers=headers, site=site, use_json=True
                    )

                    if retry_response:
                        retry_results = json.loads(retry_response)
                        retry_cards = retry_results.get("Cards", {})
                        logger.info(f"[F2F] Retry for batch {batch_index+1} found {len(retry_cards)} cards")
                        all_results["Cards"].update(retry_cards)

                # Wait between batches to avoid overwhelming the server
                if batch_index < len(batches) - 1:
                    await asyncio.sleep(1.5)

            except json.JSONDecodeError as e:
                logger.error(f"[F2F] JSON error in batch {batch_index+1}: {str(e)}")
                continue
            except Exception as e:
                logger.error(f"[F2F] Error processing batch {batch_index+1}: {str(e)}")
                continue

        # Log final results
        total_cards_found = len(all_results["Cards"])
        logger.info(f"[F2F] Total cards found across all batches: {total_cards_found}/{len(card_names)}")

        # Check how many requested cards were found
        found_requested = set(all_results["Cards"].keys()).intersection(set(card_names))
        logger.info(f"[F2F] Found {len(found_requested)} of the {len(card_names)} requested cards")

        # Copy other fields from the last response to maintain response structure
        if "batch_results" in locals() and batch_results:
            for key in batch_results:
                if key != "Cards":
                    all_results[key] = batch_results[key]

        missing_cards = set(card_names) - set(all_results["Cards"].keys())

        if missing_cards:
            logger.warning(f"[F2F] The following {len(missing_cards)} cards were not found:")
            for missing in sorted(missing_cards):
                logger.warning(f"[F2F] Missing card: {missing}")

        return all_results

    # async def search_f2f(self, site, card_names):
    #     """Submit card searches to F2F new Shopify-based API."""
    #     results = []
    #     semaphore = asyncio.Semaphore(2)  # reduce concurrency if needed

    #     headers = {
    #         "Content-Type": "application/json",
    #         "Accept": "application/json, text/plain, */*",
    #         "Origin": "https://www.facetofacegames.com",
    #         "Referer": "https://www.facetofacegames.com/deck-results/",
    #         "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    #         "Accept-Language": "en-US,en;q=0.9",
    #         "Connection": "keep-alive",
    #     }

    #     async def limited_post_request(batch_names):
    #         try:
    #             async with semaphore:
    #                 api_url = "https://facetofacegames.com/apps/prod-indexer/deckBuilder/search"
    #                 json_payload = {
    #                     "sort": False,
    #                     "filters": [
    #                         {"field": "Card Name", "values": batch_names},
    #                         {"field": "in_stock", "values": ["1"]},
    #                     ],
    #                 }
    #                 response_text = await self.network.post_request(api_url, json_payload, headers=headers, site=site)
    #                 await asyncio.sleep(2)

    #                 if response_text is None:
    #                     logger.warning(f"No response for batch: {batch_names}")
    #                     return {}

    #                 try:
    #                     card_results = json.loads(response_text)
    #                     logger.info(f"[F2F] Processed batch with {len(card_results.get('Cards', {}))} card entries.")
    #                     return card_results.get("Cards", {})
    #                 except json.JSONDecodeError:
    #                     logger.error(f"Invalid JSON response. Response (truncated): {response_text[:200]}")
    #                     return {}

    #         except Exception as e:
    #             logger.error(f"Request failed for batch: {batch_names}: {str(e)}", exc_info=True)
    #             return {}

    #     # F2F seems to support multiple cards in a single request. Chunk if needed:
    #     batch_size = 10
    #     tasks = [limited_post_request(card_name) for card_name in card_names]

    #     all_results = await asyncio.gather(*tasks, return_exceptions=True)

    #     # Flatten results from each batch
    #     for card_result in all_results:
    #         if isinstance(card_result, dict):
    #             results.extend(card_result)

    #     combined_results = {}
    #     for result in results:
    #         combined_results.update(result)

    #     if combined_results:
    #         logger.info(f"Successfully processed F2F Shopify API with {len(combined_results)} cards.")
    #         return {"Cards": combined_results}
    #     else:
    #         logger.warning(f"No valid results from F2F Shopify API for {site.name}")
    #         return None

    async def search_shopify(self, site, card_names):
        """Get card data from Shopify via Binder API"""
        try:
            _, relevant_headers = await SiteService.get_site_details(site)
            api_url, json_payload = CardService.create_shopify_url_and_payload(site, card_names)
            # logger.info(f"Shopify API URL: {api_url}")
            # logger.info(f"Shopify API Payload: {json.dumps(json_payload)}")

            response = await network.post_request(api_url, json_payload, headers=relevant_headers, site=site)

            await asyncio.sleep(2)  # Add delay to avoid rate limiting

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

    def standardize_card_dataframe(self, cards):
        df = pd.DataFrame(cards)
        # # Ensure standard column names and data types
        standard_columns = {
            "name": str,
            "set_name": str,
            "set_code": str,
            "price": float,
            "version": str,
            "foil": bool,
            "quality": str,
            "language": str,
            "quantity": int,
        }

        # Add missing columns with default values
        for col, dtype in standard_columns.items():
            if col not in df.columns:
                df[col] = dtype()
            df[col] = df[col].astype(dtype)

        df = df.drop_duplicates(subset=["name", "set_name", "quality", "foil", "price"])
        return df

    # q

    @staticmethod
    def log_cards_df_stat(site, cards_df):
        try:
            summary = (
                cards_df.groupby(["name", "foil"])
                .agg(
                    {
                        "set_name": "count",
                        "price": ["min", "max", "mean"],
                        "quantity": "sum",
                    }
                )
                .round(2)
            )

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
                    if (
                        "magic_singles" in href
                        or "cartes_individuelles_magic" in href
                        or "magic_the_gathering_singles" in href
                        or "unfinity" in href
                        or "commander_fallout" in href
                    ):
                        return True
            return False
        except Exception as e:
            logger.error(f"Error checking if product is Magic card: {str(e)}", exc_info=True)
            return False
