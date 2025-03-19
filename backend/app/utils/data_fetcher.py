import asyncio
import json
import logging
import re
import time
import traceback
import urllib
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

import pandas as pd
from app.constants import CardLanguage, CardQuality, CardVersion
from app.extensions import db
from app.services import CardService
from app.utils.helpers import (
    clean_card_name,
    extract_numbers,
    normalize_price,
    parse_card_string,
)
from app.utils.selenium_driver import NetworkDriver
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
        logger.info("\n======= Scraping Summary =======")
        for site, stats in self.site_stats.items():
            logger.info(
                f"{site}: Found {stats['found_cards']} / {stats['total_cards']} cards (Total variants: {stats['total_variants']})"
            )
            logger.info(
                f"   Search time: {stats['search_time']}s | Extract time: {stats['extract_time']}s | Total time: {stats['total_time']}s"
            )
        logger.info("================================\n")


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
    site_details_cache = {}

    def __init__(self):
        self.network = NetworkDriver()
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

        # Also make sure to properly clean up network resources
        if hasattr(self.network, "_cleanup"):
            try:
                await self.network._cleanup()
            except Exception as e:
                logger.error(f"Error cleaning up network resources: {str(e)}")

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

            logger.info(f"Processing {len(sites)} sites, grouped by scraping method.")

            async def process_group(method, method_sites):
                """Process a group of sites sharing the same method."""
                concurrency = self.network.method_limiter.get_concurrency(method)
                rate_limit = self.network.method_limiter.get_rate_limit(method)

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
            # for site in sites:
            #     concurrency = self.network.method_limiter.get_concurrency(site.method)
            #     rate_limit = self.network.method_limiter.get_rate_limit(site.method)
            #     logger.info(
            #         f"Processing {len(sites)} sites with method '{site.method}'"
            #         f" using concurrency {concurrency} and rate limit {rate_limit}/sec"
            #     )

            #     # Process sites in this domain with limited concurrency
            #     semaphore = asyncio.Semaphore(concurrency)

            #     async def process_with_limit(site):
            #         async with semaphore:
            #             return await self.process_site(site, card_names)

            #     pending_tasks = [process_with_limit(site) for site in sites]
            #     for future in asyncio.as_completed(pending_tasks):
            #         try:
            #             result = await future
            #             if result:
            #                 results.extend(result)
            #         except Exception as e:
            #             logger.error(f"Error in scraping task: {str(e)}", exc_info=True)

            #     elapsed_time = round(
            #         time.time() - start_time, 2
            #     )  # Compute elapsed time
            #     logger.info(
            #         f"Completed scraping with {len(results)} total results in {elapsed_time} seconds"
            #     )
            #     return results

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

            elif scrapping_method == ExternalDataSynchronizer.SCRAPPING_METHOD_HAWK:

                start_time_search = time.time()  # Start timing
                json_data = await self.search_hawk(site, card_names)
                elapsed_time_search = round(time.time() - start_time_search, 2)  # Compute elapsed time

                if not json_data:
                    self.error_collector.unreachable_stores.add(site.name)
                    self.log_site_error(
                        site.name,
                        "Connection Error",
                        "Failed to retrieve data from Hawk API.",
                    )
                    return None

                start_time_extract = time.time()  # Start timing
                cards_df = await self.extract_info_hawk_json(json_data, site, card_names)
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
                    f"Successfully processed {found_cards} / {total_cards} (Total: {len(cards_df)}) for {site.name} [{site.method}]"
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
                    )[["name", "set_name", "set_code", "quality", "language", "price", "quantity", "foil", "version"]]
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

    # def _extract_info_crystal_sync_vectorized(self, soup, site, card_names, scrapping_method):
    #     forms = soup.find_all("form", {"class": "add-to-cart-form"})

    #     bulk_data = [
    #         {
    #             "data-name": form.get("data-name"),
    #             "data-price": form.get("data-price"),
    #             "data-category": form.get("data-category"),
    #             "data-variant": form.get("data-variant"),
    #             "product": form.find_parent("li", {"class": "product"}),
    #             "product-link": form.find_previous("a", itemprop="url"),
    #         }
    #         for form in forms
    #     ]

    #     df = pd.DataFrame(bulk_data)
    #     df.dropna(
    #         subset=[
    #             "data-name",
    #             "data-price",
    #             "data-category",
    #             "data-variant",
    #             "product",
    #         ],
    #         inplace=True,
    #     )

    #     if df.empty:
    #         return pd.DataFrame()

    #     # Filter Magic cards
    #     df["is_magic"] = df["product"].apply(self.is_magic_card)
    #     df = df[df["is_magic"]]
    #     if df.empty:
    #         return pd.DataFrame()

    #     # Parse card names
    #     df["parsed_name"] = df["data-name"].apply(parse_card_string)
    #     df.dropna(subset=["parsed_name"], inplace=True)

    #     df["clean_name"] = df["parsed_name"].apply(lambda x: clean_card_name(x["Name"], card_names))
    #     df.dropna(subset=["clean_name"], inplace=True)

    #     excluded_categories = {
    #         "playmats",
    #         "booster packs",
    #         "booster box",
    #         "cb consignment",
    #         "mtg booster boxes",
    #         "art series",
    #         "fat packs and bundles",
    #         "mtg booster packs",
    #         "magic commander deck",
    #         "world championship deck singles",
    #         "the crimson moon's fairy tale",
    #         "rpg accessories",
    #         "scan other",
    #         "intro packs and planeswalker decks",
    #         "wall scrolls",
    #         "lots of keycards",
    #         "board games",
    #         "token colorless",
    #         "books",
    #         "pbook",
    #         "dice",
    #         "pathfinder",
    #         "oversized cards",
    #         "promos: miscellaneous",
    #         "brawl",
    #     }

    #     df["exclude"] = df["data-category"].str.lower().apply(lambda cat: any(x in cat for x in excluded_categories))
    #     df = df[~df["exclude"]]
    #     if df.empty:
    #         return pd.DataFrame()

    #     # Robust set name extraction with fallback
    #     def extract_set_name_with_fallback(row):
    #         category = row["data-category"]
    #         set_name = CardService.get_closest_set_name(category)
    #         if set_name and set_name.lower() != "unknown":
    #             return set_name

    #         product_link = row["product-link"]
    #         if product_link:
    #             product_url = product_link.get("href", "")
    #             fallback_set = CardService.extract_magic_set_from_href(product_url)
    #             if fallback_set:
    #                 logger.info(f"Fallback used for set '{category}' -> '{fallback_set}' using URL: {product_url}")
    #                 return fallback_set

    #         logger.warning(
    #             f"No valid fallback set found for '{category}' with URL: {product_url if product_link else 'None'}"
    #         )
    #         return None

    #     df["set_name"] = df.apply(extract_set_name_with_fallback, axis=1)
    #     df.dropna(subset=["set_name"], inplace=True)

    #     # Map set codes
    #     unique_set_names = df["set_name"].unique()
    #     set_code_mapping = {sn: CardService.get_clean_set_code(sn) for sn in unique_set_names}
    #     df["set_code"] = df["set_name"].map(set_code_mapping)

    #     # Explicitly exclude unknown set codes
    #     df = df[df["set_code"].str.lower() != "unknown"]
    #     if df.empty:
    #         return pd.DataFrame()

    #     # Extract quality and language
    #     df[["quality", "language"]] = df["data-variant"].apply(self.extract_quality_language).tolist()

    #     # Numeric conversions
    #     df["price"] = pd.to_numeric(df["data-price"].replace("[^\d.]", "", regex=True), errors="coerce")
    #     df["quantity"] = df["product"].apply(self.extract_quantity).fillna(1).infer_objects(copy=False).astype(int)

    #     # Parse name, version, foil status
    #     df[["unclean_name", "version", "foil"]] = df["data-name"].apply(self.find_name_version_foil).tolist()
    #     df["foil"] = df.apply(
    #         lambda row: self.detect_foil(row["foil"], row["version"], row["data-variant"]),
    #         axis=1,
    #     )
    #     df["version"] = df["version"].fillna("Standard").apply(CardVersion.normalize)

    #     final_df = (
    #         df[
    #             [
    #                 "clean_name",
    #                 "set_name",
    #                 "set_code",
    #                 "quality",
    #                 "language",
    #                 "price",
    #                 "quantity",
    #                 "foil",
    #                 "version",
    #             ]
    #         ]
    #         .rename(columns={"clean_name": "name"})
    #         .drop_duplicates()
    #     )

    #     # Ensure standard column names and types
    #     standard_columns = {
    #         "name": str,
    #         "set_name": str,
    #         "set_code": str,
    #         "quality": str,
    #         "language": str,
    #         "price": float,
    #         "quantity": int,
    #         "foil": bool,
    #         "version": str,
    #     }

    #     for col, dtype in standard_columns.items():
    #         if col not in final_df.columns:
    #             final_df[col] = dtype()
    #         final_df[col] = final_df[col].astype(dtype)

    #     return final_df.reset_index(drop=True)

    # async def extract_info_crystal_scrapper(self, soup, site, card_names, scrapping_method):
    #     """Extract card information with non-blocking execution"""

    #     # Run the CPU-intensive operations in a thread pool
    #     return await self.process_dataframe(
    #         self._extract_info_crystal_scrapper_sync, soup, site, card_names, scrapping_method
    #     )

    # def _extract_info_crystal_scrapper_sync(self, soup, site, card_names, scrapping_method):
    #     """
    #     Extract card information using either form-based or scrapper scrapping_method.
    #     """

    #     excluded_categories = {
    #         "playmats",
    #         "booster packs",
    #         "booster box",
    #         "cb consignment",
    #         "mtg booster boxes",
    #         "art series",
    #         "fat packs and bundles",
    #         "mtg booster packs",
    #         "magic commander deck",
    #         "world championship deck singles",
    #         "the crimson moon's fairy tale",
    #         "rpg accessories",
    #         "scan other",
    #         "intro packs and planeswalker decks",
    #         "wall scrolls",
    #         "lots of keycards",
    #         "board games",
    #         "token colorless",
    #         "scan other",
    #         "books",
    #         "pbook",
    #         "dice",
    #         "pathfinder",
    #         "oversized cards",
    #         "promos: miscellaneous",
    #         "brawl",
    #     }
    #     promo_set_mappings = {
    #         "CBL Bundle Promo": "Commander Legends: Battle for Baldur's Gate",
    #         "Treasure Chest Promo": "ixalan promos",
    #         "Bundle Promo": "Promo Pack",  # Generic bundle promos
    #     }

    #     if soup is None:
    #         logger.warning(f"Soup is None for site {site.name}")
    #         return pd.DataFrame()

    #     cards = []
    #     seen_variants = set()
    #     # Original scrapper strategy with enhanced validation
    #     content = soup.find(
    #         "div",
    #         {"class": ["content", "content clearfix", "content inner clearfix"]},
    #     )
    #     if content is None:
    #         logger.error(f"Content div not found for site {site.name}")
    #         return pd.DataFrame()

    #     products_containers = content.find_all("div", {"class": "products-container browse"})
    #     if not products_containers:
    #         logger.warning(f"No variants container found for site {site.name}")
    #         return pd.DataFrame()

    #     for container in products_containers:
    #         products = container.find_all("li", {"class": "product"})
    #         for product in products:
    #             if not self.is_magic_card(product):
    #                 logger.debug(f"Skipping non-Magic card product")
    #                 continue
    #             variants_section = product.find("div", {"class": "variants"})
    #             if not variants_section:
    #                 continue

    #             for variant in variants_section.find_all("div", {"class": "variant-row"}):
    #                 if "no-stock" in variant.get("class", []):
    #                     continue
    #                 try:
    #                     # Extract and validate quality and language
    #                     variant_data = variant.find(
    #                         "span",
    #                         {"class": "variant-short-info variant-description"},
    #                     ) or variant.find("span", {"class": "variant-short-info"})

    #                     if not variant_data:
    #                         continue

    #                     # Get set name
    #                     meta_div = product.find("div", {"class": "meta"})
    #                     if not meta_div:
    #                         logger.warning(f"Meta div not found for variant")
    #                         continue

    #                     # Get and validate name
    #                     name_header = meta_div.find("h4", {"class": "name"}) if meta_div else None
    #                     if not name_header:
    #                         logger.warning(f"Name header not found for variant")
    #                         continue

    #                     parsed_card = parse_card_string(name_header.text)
    #                     if not parsed_card:
    #                         logger.warning(f"Failed to parse card name: {name_header.text}")
    #                         continue

    #                     clean_name = clean_card_name(parsed_card.get("Name", name_header.text), card_names)
    #                     if not clean_name or (
    #                         clean_name not in card_names and clean_name.split(" // ")[0].strip() not in card_names
    #                     ):
    #                         logger.debug(f"Invalid card name: {clean_name}")
    #                         continue

    #                     # Extract and validate quality and language
    #                     quality_language = ExternalDataSynchronizer.normalize_variant_description(variant_data.text)
    #                     # logger.info(f"after normalize_variant_description: {quality_language}")
    #                     quality, language = self.extract_quality_language(quality_language)

    #                     if not quality or not language:
    #                         logger.warning(f"Quality or language not found for variant{quality_language}")
    #                         continue

    #                     # Extract and validate quantity
    #                     quantity = self.extract_quantity(variant)
    #                     if quantity is None or quantity <= 0:
    #                         logger.warning(f"Invalid quantity for variant: {quantity}")
    #                         continue

    #                     # Extract and validate price
    #                     price = self.extract_price(variant)
    #                     if price is None or price <= 0:
    #                         logger.warning(f"Invalid price for variant: {price}")
    #                         continue

    #                     set_elem = meta_div.find("span", {"class": "category"}) if meta_div else None
    #                     if not set_elem:
    #                         logger.warning(f"Set element not found for variant")
    #                         continue

    #                     if any(cat in set_elem.text.lower() for cat in excluded_categories):
    #                         logger.warning(f"Excluded category found: {set_elem.text}")
    #                         continue

    #                     set_name = CardService.get_closest_set_name(set_elem.text.lower())
    #                     if not set_name:
    #                         logger.warning(f"Failed to get set name for variant: {set_elem.text}")
    #                         continue
    #                     set_code = CardService.get_clean_set_code(set_name)
    #                     if not set_code:
    #                         logger.warning(f"Failed to get set code for variant: {set_code}")
    #                         continue

    #                     # Determine foil status and version
    #                     is_foil = parsed_card.get("Foil", False)
    #                     version = CardVersion.normalize(parsed_card.get("Version", "Standard"))
    #                     if not version:
    #                         logger.warning(f"Failed to get version for variant: {parsed_card}")
    #                         continue

    #                     card_info = {
    #                         "name": clean_name,
    #                         "set_name": set_name,
    #                         "set_code": set_code,
    #                         "quality": quality,
    #                         "language": language,
    #                         "price": price,
    #                         "quantity": quantity,
    #                         "foil": is_foil,
    #                         "version": version,
    #                     }

    #                     # Deduplicate variants
    #                     variant_key = (
    #                         card_info["name"],
    #                         card_info["set_name"],
    #                         card_info["set_code"],
    #                         card_info["quality"],
    #                         card_info["language"],
    #                         card_info["foil"],
    #                         card_info["version"],
    #                     )
    #                     if variant_key not in seen_variants:
    #                         cards.append(card_info)
    #                         seen_variants.add(variant_key)

    #                 except Exception as e:
    #                     logger.error(f"Error processing variant: {str(e)}", exc_info=True)
    #                     continue

    #     if not cards:
    #         logger.warning(f"No valid cards found for {site.name}")
    #         return pd.DataFrame()

    #     try:
    #         df = pd.DataFrame(cards)

    #         # Ensure standard column names and data types
    #         standard_columns = {
    #             "name": str,
    #             "set_name": str,
    #             "price": float,
    #             "version": str,
    #             "foil": bool,
    #             "quality": str,
    #             "language": str,
    #             "quantity": int,
    #         }

    #         # Add missing columns with default values and convert types
    #         for col, dtype in standard_columns.items():
    #             if col not in df.columns:
    #                 df[col] = dtype()
    #             df[col] = df[col].astype(dtype)

    #         return df

    #     except Exception as e:
    #         logger.error(f"Error creating DataFrame for {site.name}: {str(e)}", exc_info=True)
    #         return pd.DataFrame()

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
                                logger.info(
                                    f"Fallback set code found from data-name part '{part}': {fallback_set_name} ({fallback_set_code})"
                                )
                                set_code = fallback_set_code
                                set_name = fallback_set_name
                                break
                        if not set_code:
                            logger.info(
                                f"[SET CODE] Skipping card {name} unknown set: {set_code} for site: {site.name}\n {data}"
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

                    quality, language = self.extract_quality_language(test)
                    # logger.info(f"after extract_quality_language form: {quality} ")

                    # Parse name, version, and foil status
                    unclean_name, version, foil = self.find_name_version_foil(data["data-name"])
                    is_foil = self.detect_foil(product_foil=foil, product_version=version, variant_data=test)
                    version = CardVersion.normalize(version or "Standard")

                    # Extract and validate quantity
                    quantity = self.extract_quantity(form)
                    if not quantity or quantity <= 0:
                        quantity = 1

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
                            quality_language = ExternalDataSynchronizer.normalize_variant_description(variant_data.text)
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
                            set_code = CardService.get_clean_set_code_from_set_name(set_name)
                            if not set_code:
                                # Attempt fallback using parts of data-name
                                name_parts = name_header.split(" - ")
                                for part in reversed(name_parts):  # Start from the most specific suffix
                                    fallback_set_name = CardService.get_closest_set_name(part.strip())
                                    fallback_set_code = CardService.get_clean_set_code_from_set_name(fallback_set_name)
                                    if fallback_set_code:
                                        logger.info(
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
            logger.info(f"[CRYSTAL] Processed {len(df)} unique variants for {len(df['name'].unique())} distinct cards")
            return df
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

            # # Add missing columns with default values and convert types
            # for col, dtype in standard_columns.items():
            #     if col not in df.columns:
            #         df[col] = dtype()
            #     df[col] = df[col].astype(dtype)

            # return df

        except Exception as e:
            logger.error(f"Error creating DataFrame for {site.name}: {str(e)}", exc_info=True)
            return pd.DataFrame()

    async def extract_info_hawk_json(self, json_data, site, card_names):
        """Extract card information from Hawk API response with non-blocking execution"""
        return await self.process_dataframe(self._extract_info_hawk_json_sync, json_data, site, card_names)

    def _extract_info_hawk_json_sync(self, json_data, site, card_names):
        """Extract card information from Hawk API response with deduplication"""
        if not json_data:
            logger.warning(f"No results in Hawk response for {site.name}")
            return pd.DataFrame()
        if "Results" not in json_data:
            logger.warning(f"No results in Hawk response for {site.name}")
            truncated_json_data = (
                json.dumps(json_data)[:300] + "..." if len(json.dumps(json_data)) > 300 else json.dumps(json_data)
            )
            logger.warning(f"json_data (truncated): {truncated_json_data}")

            return pd.DataFrame()

        cards = []
        processed_cards = set()  # Track unique card variants

        try:
            # Process each result
            for result in json_data["Results"]:
                if not result.get("Document"):
                    continue

                doc = result["Document"]

                # Get basic card info
                card_name = doc.get("card name", [""])[0]
                if not card_name or card_name not in card_names:
                    continue

                # Process child attributes (variants)
                child_attrs = doc.get("hawk_child_attributes_hits", [])
                for child_attr_group in child_attrs:
                    for item in child_attr_group.get("Items", []):
                        try:
                            # Extract condition and finish
                            option_condition = item.get("option_condition", ["NM"])[0]
                            option_finish = item.get("option_finish", ["Non-Foil"])[0]

                            # Extract price and inventory
                            price = float(item.get("child_price_sort_bc", ["0.0"])[0])
                            inventory = int(item.get("child_inventory_level", ["0"])[0])

                            if inventory <= 0:
                                continue

                            # Create unique identifier for deduplication
                            variant_key = (
                                card_name,
                                doc.get("set", [""])[0],
                                option_condition,
                                "Foil" in option_finish,
                                price,
                            )

                            # Skip if we've already processed this variant
                            if variant_key in processed_cards:
                                continue

                            processed_cards.add(variant_key)

                            # Create card info dictionary
                            quality = CardQuality.normalize(option_condition)
                            set_name = doc.get("set", [""])[0]
                            set_code = doc.get("set_code", [""])[0]
                            if not set_code or set_code == "":
                                test_code = CardService.get_clean_set_code_from_set_name(set_name)
                                if not test_code:
                                    logger.warning(
                                        f"[SET CODE] Failed to get set code for set name: {set_name}, Skipping"
                                    )
                                    continue
                                set_code = test_code
                                logger.debug(
                                    f"[HAWK] set_code was empty for {card_name} used set name to get it: {test_code}"
                                )
                            card_info = {
                                "name": card_name,
                                "set_name": set_name,
                                "set_code": set_code,
                                "language": "English",  # Default for F2F
                                "version": "Standard",
                                "foil": "Foil" in option_finish,
                                "quality": quality,
                                "quantity": inventory,
                                "price": price,
                            }
                            cards.append(card_info)

                        except Exception as e:
                            logger.error(
                                f"Error processing variant for {card_name} in {site.name}: {str(e)}",
                                exc_info=True,
                            )
                            continue

            if not cards:
                logger.warning(f"No valid cards found in Hawk response for {site.name}")
                return pd.DataFrame()

            # # Convert to DataFrame
            # df = pd.DataFrame(cards)

            # # Normalize quality values
            # df["quality"] = df["quality"].apply(CardQuality.normalize)

            # # Remove any remaining duplicates
            # df = df.drop_duplicates(subset=["name", "set_name", "quality", "foil", "price"])

            # logger.info(f"Processed {len(df)} unique variants for {len(df['name'].unique())} distinct cards")

            # return df

            df = self.standardize_card_dataframe(cards)
            logger.info(f"[HAWK] Processed {len(df)} unique variants for {len(df['name'].unique())} distinct cards")
            return df

        except Exception as e:
            logger.error(f"Error processing Hawk JSON for {site.name}: {str(e)}", exc_info=True)
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
                                    f"[SET CODE] Skipping card {name} unknown set: {test_code} for site: {site.name}"
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

    async def get_site_details(self, site, auth_required=True):
        if site.name in self.site_details_cache:
            logger.info(f"Using cached site details for {site.name}")
            return self.site_details_cache[site.name]
        auth_token = None
        search_url = site.url.rstrip("/")
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
                    if key.lower()
                    in [
                        "cache-control",
                        "content-type",
                        "accept-language",
                        "accept-encoding",
                    ]
                }
            cookies = site_details.get("cookies", {})
            if isinstance(cookies, dict):
                cookie_str = "; ".join([f"{key}={value}" for key, value in cookies.items()])

            self.site_details_cache[site.name] = (
                auth_token,
                relevant_headers,
                cookie_str,
            )
            return auth_token, relevant_headers, cookie_str

        except Exception as e:
            logger.error(
                f"Error in crystal commerce search for {site.name}: {str(e)}",
                exc_info=True,
            )
            return None

    async def _search_crystal_batch(self, site, batch_card_names, search_url, auth_token, relevant_headers):
        """
        Simplified crystal commerce search with better error handling.
        """
        max_retries = 3
        retry_count = 0
        backoff_factor = 1

        while retry_count < max_retries:
            try:
                retry_count += 1
                logger.debug(f"Attempting batch search for {site.name} (attempt {retry_count}/{max_retries})")

                query_string = "\r\n".join(batch_card_names)
                if "orchardcitygames" in site.name.lower():
                    query_string = urllib.parse.quote_plus(query_string)

                payload = {
                    "authenticity_token": auth_token,
                    "query": query_string,
                    "submit": "Continue",
                }

                # Copy headers to avoid modifying the original
                request_headers = dict(relevant_headers)

                # Add some additional headers that might help with connection issues
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

                # Make the request with an increased timeout
                response = await self.network.post_request(search_url, payload, headers=request_headers, site=site)

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

        # Get site details including authentication token and headers
        search_url = site.url.rstrip("/")

        try:
            site_details = await self.get_site_details(site)
            if not site_details:
                logger.error(f"Failed to get site details for {site.name}")
                return None

            auth_token, relevant_headers, cookie_str = site_details

            relevant_headers.update(
                {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                    "Cookie": cookie_str,
                }
            )

            # Prepare search payload
            clean_names = [clean_card_name(name, card_names) for name in card_names if name]

            if not clean_names:
                logger.error(f"No valid card names to search for {site.name}")
                return None

            # Split the card list into chunks of BATCH_SIZE
            card_batches = [clean_names[i : i + BATCH_SIZE] for i in range(0, len(clean_names), BATCH_SIZE)]

            # Prepare tasks for all batches
            tasks = [
                self._search_crystal_batch(site, batch, search_url, auth_token, relevant_headers)
                for batch in card_batches
            ]

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

    async def search_hawk(self, site, card_names):
        """Submit individual card searches to Hawk API with proper name formatting"""
        results = []
        semaphore = asyncio.Semaphore(4)
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://www.facetofacegames.com",
            "Referer": "https://www.facetofacegames.com/deck-results/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
        }

        async def limited_post_request(card_name):
            try:
                async with semaphore:
                    api_url, json_payload = CardService.create_hawk_url_and_payload(site, card_name)
                    await asyncio.sleep(0.4)  # pacing delay

                    response_text = await self.network.post_request(api_url, json_payload, headers=headers, site=site)

                    if response_text is None:
                        logger.warning(f"No response for card: {card_name}")
                        return []

                    try:
                        card_results = json.loads(response_text)
                        found_results = card_results.get("Results", [])
                        logger.info(f"[HAWK] Processed {card_name} with {len(found_results)} results.")
                        return found_results
                    except json.JSONDecodeError:
                        logger.error(
                            f"Invalid JSON response for {card_name}. Response (truncated): {response_text[:200]}"
                        )
                        return []

            except Exception as e:
                logger.error(f"Request failed for {card_name}: {str(e)}", exc_info=True)
                return []

        tasks = [limited_post_request(card_name) for card_name in card_names]
        all_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Flatten results and filter out exceptions
        for result in all_results:
            if isinstance(result, list):
                results.extend(result)

        if results:
            logger.info(f"Successfully processed Hawk API with {len(results)} total results")
            return {"Results": results}
        else:
            logger.warning(f"No valid results from Hawk API for {site.name}")
            return None
            # for card_name in card_names:

            #     api_url, json_payload = CardService.create_hawk_url_and_payload(
            #         site, card_name
            #     )
            #     # Debug logging
            #     # logger.info(f"Hawk API Request for {card_name}:")
            #     # logger.info(f"URL: {api_url}")
            #     # logger.info(f"Payload: {json_payload}")

            #     # Add delay between requests
            #     if results:  # Skip delay for first request
            #         await asyncio.sleep(0.5)

            #     try:
            #         # Add use_json=True parameter here
            #         response_text = await self.network.post_request(
            #             api_url, json_payload, headers=headers, method=site.method
            #         )

            #         if response_text is None:
            #             logger.error(
            #                 f"Request failed for {card_name}: No response received"
            #             )
            #             continue

            #         try:
            #             card_results = json.loads(response_text)
            #             if card_results and "Results" in card_results:
            #                 results.extend(card_results["Results"])
            #                 logger.debug(
            #                     f"[HAWK] Successfully processed {card_name} with {len(card_results['Results'])} results"
            #                 )
            #             else:
            #                 logger.warning(
            #                     f"[HAWK] No results for {card_name}, Response: {response_text[:200]}"
            #                 )
            #         except json.JSONDecodeError as e:
            #             logger.error(
            #                 f"Invalid JSON response for {card_name}: {str(e)}",
            #                 exc_info=True,
            #             )
            #             logger.error(f"Raw response: {response_text[:200]}")
            #             continue

            #         await asyncio.sleep(0.5)  # Add delay to avoid rate limiting

            #     except Exception as e:
            #         logger.error(
            #             f"Request failed for {card_name}: {str(e)}", exc_info=True
            #         )
            #         continue

            # if results:
            #     logger.info(
            #         f"Successfully processed Hawk API with {len(results)} total results"
            #     )
            #     return {"Results": results}

            # logger.error(f"No valid results from Hawk API for {site.name}")
            # return None

    async def search_shopify(self, site, card_names):
        """Get card data from Shopify via Binder API"""
        try:
            _, relevant_headers, cookie_str = await self.get_site_details(site, auth_required=False)
            api_url, json_payload = CardService.create_shopify_url_and_payload(site, card_names)
            # logger.info(f"Shopify API URL: {api_url}")
            # logger.info(f"Shopify API Payload: {json.dumps(json_payload)}")

            relevant_headers.update(
                {
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                    "Cookie": cookie_str,
                }
            )

            response = await self.network.post_request(api_url, json_payload, headers=relevant_headers, site=site)

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

    @staticmethod
    def parse_shopify_variant_title(title):
        """Parse title in format 'Card Name [Set Name] Quality [Foil]'"""
        try:
            # Extract set name (content between square brackets)
            set_match = re.search(r"\[(.*?)\]", title)
            if not set_match:
                return None

            set_name = set_match.group(1).strip()

            # Remove the set name part to process the rest
            remaining = title.split("]")[-1].strip()

            # Determine if foil
            is_foil = "Foil" in remaining

            # Extract quality (everything before "Foil" or the end)
            quality = remaining.replace("Foil", "").strip()

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

            check_strings = [s.lower() for s in [product_foil, product_version, variant_data] if s is not None]

            return any("foil" in s for s in check_strings)
        except Exception as e:
            logger.exception(f"Error in detect_foil {str(e)}", exc_info=True)
            return None

    @staticmethod
    def extract_price(variant):
        """Modified to handle both dict and object card data"""
        try:
            price_elem = (
                variant.find("span", {"class": "regular price"})
                or variant.find("span", {"class": "price"})
                or variant.find("span", {"class": "variant-price"})
            )

            if not price_elem:
                logger.debug("No price element found in variant")
                return None

            price_text = price_elem.text.strip()

            # Remove currency symbols and normalize
            price_value = normalize_price(price_text)
            if not price_value or price_value < 0:
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
                return "DMG", "Unknown"  # Default values for empty input

            # Convert to string if list is passed
            if isinstance(quality_language, list):
                quality_language = ", ".join(str(x) for x in quality_language)
            elif not isinstance(quality_language, str):
                return "DMG", "Unknown"  # Default values for non-string input

            # Handle specific cases
            if "Website Exclusive" in quality_language:
                variant_parts = quality_language.split(",", 1)
                if len(variant_parts) > 1:
                    quality_language = variant_parts[1].strip()

            quality_parts = quality_language.split(",")
            if len(quality_parts) >= 2:
                raw_quality = quality_parts[0].strip()
                raw_language = quality_parts[1].strip()
            else:
                # If no comma found, assume quality is the whole string and language is English
                raw_quality = quality_language.strip()
                raw_language = "Unknown"

            # Handle special cases
            if raw_language == "SIGNED by artist":
                logger.info(f"Signed card found for variant {quality_language}")
                raw_language = "Unknown"

            quality = CardQuality.normalize(raw_quality)
            language = CardLanguage.normalize(raw_language)

            return quality or "DMG", language or "Unknown"

        except Exception as e:
            logger.exception(
                f"Error in extract_quality_language with input '{quality_language}': {str(e)}",
                exc_info=True,
            )
            return "DMG", "Unknown"  # Return default values on error

    @staticmethod
    def extract_quantity(variant):
        try:
            # Check for quantity in various formats
            qty_elem = (
                variant.find("span", {"class": "variant-short-info variant-qty"})
                or variant.find("span", {"class": "variant-short-info"})
                or variant.find("span", {"class": "variant-qty"})
                or variant.find("input", {"class": "qty", "type": "number"})
            )

            if not qty_elem:
                # logger.info(f"No quantity element found in variant {variant}")
                return None

            # Convert to integer and validate
            try:
                # Handle different quantity formats
                if qty_elem.name == "input":
                    # Check both max attribute and value
                    qty = qty_elem.get("max") or qty_elem.get("value")
                    quantity = int(qty) if qty else 0
                else:
                    # logger.info(f"Quantity element: {qty_elem}")
                    qty_text = qty_elem.text.strip()
                    # Extract numbers from text (e.g., "5 in stock" -> "5")
                    quantity = extract_numbers(qty_text)
                    # logger.info(f"Quantity text: {qty_text} -> {quantity}: {type(quantity)}")

                if quantity <= 0:
                    logger.debug(f"Quantity {quantity} is negative...")
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
                    version_part = re.sub(r"\bfoil\b", "", item, flags=re.IGNORECASE).strip()
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
