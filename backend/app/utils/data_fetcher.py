import asyncio
import json
import logging
import re
import time
import urllib
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

import pandas as pd
from app.models.site_statistics import SiteStatistics, SiteScrapeStats
from app.constants import CardQuality, CardVersion
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
from app.utils.async_context_manager import managed_network_driver
from app.utils.selenium_driver import get_network_driver
from bs4 import BeautifulSoup

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


class CardSkipTracker:
    def __init__(self):
        self.skipped_cards = []

    def add(self, site_name, card_name, reason, raw_data=None):
        self.skipped_cards.append(
            {
                "site": site_name,
                "card": card_name,
                "reason": reason,
                "raw": raw_data,
            }
        )

    def log_all(self):
        if not self.skipped_cards:
            return
        logger.warning("=" * 100)
        logger.warning("Skipped Cards Summary:")
        for entry in self.skipped_cards:
            logger.warning(
                f"[{entry['site']}] '{entry['card']}' skipped due to: {entry['reason']}\n" f"↪ Raw: {entry['raw']}"
            )
        logger.warning("=" * 100)


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
    scrapping_method_name = {
        SCRAPPING_METHOD_CRYSTAL: "crystal",
        SCRAPPING_METHOD_SCRAPPER: "scrapper",
        SCRAPPING_METHOD_F2F: "f2f",
        SCRAPPING_METHOD_SHOPIFY: "shopify",
        SCRAPPING_METHOD_OTHER: "other",
    }

    def __init__(self):
        self.error_collector = ErrorCollector.get_instance()
        self.error_collector.reset()
        # Create a thread pool for CPU-intensive operations
        self.thread_pool = ThreadPoolExecutor(max_workers=8)
        self._initialized_site_cache = set()
        self.skip_tracker = CardSkipTracker()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Clean up thread pool resources
        try:
            self.thread_pool.shutdown(wait=True)
            logger.debug("Thread pool shutdown complete")
        except Exception as e:
            logger.error(f"Error shutting down resources: {str(e)}")

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

    async def process_site(
        self,
        site_data,
        card_names,
        scrape_stats: SiteScrapeStats,
        progress_increment,
        celery_task=None,
        progress_callback=None,
    ):
        """Process a single site and return results without saving to DB

        Args:
            site_data: Dictionary containing site information (id, name, method, url, api_url)
            card_names: List of card names to search for
            scrape_stats: Stats object to record site scraping statistics
            progress_increment: Progress increment for Celery task
            celery_task: Optional Celery task for progress tracking

        Returns:
            List of card results or None if no results
        """
        self.skip_tracker = CardSkipTracker()
        # Create a dedicated network driver for this site's processing
        async with managed_network_driver(get_network_driver) as network:
            start_time = time.time()  # Start timing
            elapsed_time_search = 0
            elapsed_time_extract = 0

            # Extract site information from dictionary
            site_id = site_data["id"]
            site_name = site_data["name"]
            site_method = site_data["method"].lower()
            site_url = site_data["url"]
            site_api_url = site_data.get("api_url")

            scrapping_method = ExternalDataSynchronizer.scrapping_method_dict.get(
                site_method, ExternalDataSynchronizer.SCRAPPING_METHOD_CRYSTAL
            )

            logger.info(f"Processing site: {site_name} [{site_method}] ({len(card_names)} cards)")
            # logger.info(f"\t o Strategy: {site_method}")
            # logger.info(f"\t o URL: {site_url}")
            # if site_api_url:
            #     logger.info(f"\t o API URL: {site_api_url}")

            try:
                if scrapping_method == ExternalDataSynchronizer.SCRAPPING_METHOD_SHOPIFY:
                    # Get data from Shopify API
                    start_time_search = time.time()  # Start timing
                    json_data = await self.search_shopify(site_data, card_names, network)
                    elapsed_time_search = round(time.time() - start_time_search, 2)  # Compute elapsed time

                    if not json_data:
                        self.error_collector.unreachable_stores.add(site_name)
                        self.log_site_error(
                            site_name,
                            "Connection Error",
                            "Failed to retrieve data from Shopify API.",
                        )
                        return None

                    start_time_extract = time.time()  # Start timing
                    cards_df = await self.extract_info_shopify_json(json_data, site_data, card_names)
                    elapsed_time_extract = round(time.time() - start_time_extract, 2)  # Compute elapsed time

                elif scrapping_method == ExternalDataSynchronizer.SCRAPPING_METHOD_F2F:
                    start_time_search = time.time()  # Start timing
                    json_data = await self.search_f2f(site_data, card_names, network)
                    elapsed_time_search = round(time.time() - start_time_search, 2)  # Compute elapsed time

                    if not json_data:
                        self.error_collector.unreachable_stores.add(site_name)
                        self.log_site_error(
                            site_name,
                            "Connection Error",
                            "Failed to retrieve data from f2f API.",
                        )
                        return None

                    start_time_extract = time.time()  # Start timing
                    cards_df = await self.extract_info_f2f_json(json_data, site_data, card_names)
                    elapsed_time_extract = round(time.time() - start_time_extract, 2)  # Compute elapsed time

                else:
                    start_time_search = time.time()  # Start timing
                    soup = await self.search_crystalcommerce(site_data, card_names, network)
                    elapsed_time_search = round(time.time() - start_time_search, 2)  # Compute elapsed time

                    if not soup:
                        self.error_collector.unreachable_stores.add(site_name)
                        self.log_site_error(
                            site_name,
                            "Connection Error",
                            "Failed to retrieve data from site. Site may be down or blocking requests.",
                        )
                        return None

                    start_time_extract = time.time()  # Start timing
                    cards_df = await self.extract_info_crystal(soup, site_data, card_names, scrapping_method)
                    elapsed_time_extract = round(time.time() - start_time_extract, 2)  # Compute elapsed time

                    if cards_df.empty:
                        old_strategy = scrapping_method
                        scrapping_method = (
                            ExternalDataSynchronizer.SCRAPPING_METHOD_SCRAPPER
                            if scrapping_method == ExternalDataSynchronizer.SCRAPPING_METHOD_CRYSTAL
                            else ExternalDataSynchronizer.SCRAPPING_METHOD_CRYSTAL
                        )
                        logger.info(
                            f"Strategy {ExternalDataSynchronizer.scrapping_method_name[old_strategy]} failed, "
                            f"attempting with {ExternalDataSynchronizer.scrapping_method_name[scrapping_method]}"
                        )
                        start_time_extract = time.time()  # Start timing
                        cards_df = await self.extract_info_crystal(soup, site_data, card_names, scrapping_method)
                        elapsed_time_extract = round(time.time() - start_time_extract, 2)  # Compute elapsed time

                if cards_df is None or cards_df.empty:
                    self.log_site_error(
                        site_name,
                        f"No Data Found {site_method}",
                        f"Strategy '{site_method}' failed to extract any valid card data",
                    )
                    return None

                if cards_df is not None and not cards_df.empty:
                    # Create summary of results
                    total_cards = len(card_names)
                    found_cards = cards_df["name"].nunique()
                    elapsed_time = round(time.time() - start_time, 2)  # Compute elapsed time

                    logger.info(
                        f"Successfully processed {site_name} [{site_method}] found {found_cards} / {total_cards} ({len(cards_df)} total variants)"
                    )

                    # Record into scrape_stats
                    scrape_stats.record_site(
                        site_id=site_data["id"],
                        site_name=site_data["name"],
                        search_time=elapsed_time_search,
                        extract_time=elapsed_time_extract,
                        total_time=elapsed_time,
                        found_cards=found_cards,
                        total_cards=total_cards,
                        total_variants=len(cards_df),
                    )

                    # Convert DataFrame rows to results
                    results = (
                        cards_df.rename(
                            columns={"clean_name": "name"}
                        )  # Only if necessary, ensure correct column mapping
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

                    # Add site information to results
                    for r in results:
                        r["site_id"] = site_id
                        r["site_name"] = site_name

                    logger.info(
                        f"Updating progress for {site_name} from {celery_task.progress} to {celery_task.progress + progress_increment}"
                    )

                    progress_fraction = found_cards / total_cards if total_cards > 0 else 0
                    increment = progress_fraction * 100  # Scale to percentage
                    if progress_callback:
                        progress_callback(increment, total_cards)

                    return results
                else:
                    logger.warning(f"No valid cards found for {site_name}")
                    return None

            except Exception as e:
                elapsed_time = round(time.time() - start_time, 2)
                self.log_site_error(site_name, f"Processing Error (after {elapsed_time} seconds)", str(e))
                return None

    async def extract_info_crystal(self, soup, site, card_names, scrapping_method):
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
            logger.warning(f"Soup is None for site {site.get('name')}")
            return pd.DataFrame()

        cards = []
        seen_variants = set()
        total_variant = 0

        if scrapping_method == self.SCRAPPING_METHOD_CRYSTAL:
            # Form-based extraction focusing on add-to-cart forms
            forms = soup.find_all("form", {"class": "add-to-cart-form"})
            if not forms:
                logger.warning(f"No add-to-cart forms found for site {site.get('name')}")
                forms = soup.find_all("form", {"class": "add-to-cart-form"})
            total_variant = len(forms)
            for form in forms:
                try:
                    product = form.find_parent("li", {"class": "product"})
                    if not product:
                        # self.skip_tracker.add(
                        #     site.get("name"), locals().get("name", "<unknown>"), "Product could not be found", data
                        # )
                        continue

                    # Check if it's a Magic card
                    if not self.is_magic_card(product):
                        # self.skip_tracker.add(
                        #     site.get("name"), locals().get("name", "<unknown>"), "Non Magic card", data
                        # )
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
                        # self.skip_tracker.add(
                        #     site.get("name"), locals().get("name", "<unknown>"), "Attributes could not be found", data
                        # )
                        continue

                    current_card = parse_card_string(data["data-name"])
                    if not current_card:
                        # self.skip_tracker.add(
                        #     site.get("name"), locals().get("name", "<unknown>"), "current_card could not be found", data
                        # )
                        continue

                    # Clean and validate card name
                    name = clean_card_name(current_card["Name"], card_names)
                    name_variants = [name, name.split(" // ")[0].strip()]
                    # logger.info(f"after clean_card_name form: {name} ")
                    # Check if any variant is in card_names directly
                    if not any(variant in card_names for variant in name_variants):
                        # If not, check case-insensitive match
                        lower_card_names = [c.lower() for c in card_names]
                        if not any(variant.lower() in lower_card_names for variant in name_variants):
                            # self.skip_tracker.add(
                            #     site.get("name"), locals().get("name", "<unknown>"), "Card not in requested list", data
                            # )
                            # logger.info(f"[CRYSTAL][SKIP] No match for: '{name}' → variants: {name_variants}")
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
                                set_name = await CardService.extract_magic_set_from_href(product_url)
                                # logger.info(f"product_url: {product_url} for site: {site.name}\n {set_name}")
                        elif category == "Promos: Miscellaneous":
                            card_name = data.get("data-name", "")
                            name_parts = card_name.split(" - ")
                            promo_suffix = name_parts[-1] if len(name_parts) > 1 else None
                            if promo_suffix and promo_suffix in promo_set_mappings:
                                set_name = promo_set_mappings[promo_suffix]
                        # self.skip_tracker.add(
                        #     site.get("name"), locals().get("name", "<unknown>"), f"Excluded category: {category}", data
                        # )
                        continue

                    # Try to match with closest set name using CardService
                    set_name = await CardService.get_closest_set_name(set_name)

                    if not set_name or set_name.lower() == "unknown":
                        original_set_name = set_name
                        # Fallback to extracting from URL (new logic)
                        product_link = form.find_previous("a", itemprop="url")
                        if product_link:
                            product_url = product_link.get("href", "")
                            fallback_set = await CardService.extract_magic_set_from_href(product_url)
                            if fallback_set:
                                set_name = fallback_set
                                logger.info(
                                    f"[SET CODE] Fallback used for set '{original_set_name}' -> '{set_name}' using URL: {product_url}"
                                )
                            else:
                                # self.skip_tracker.add(
                                #     site.get("name"), name, f"Fallback used for set for: {set_name}", data
                                # )
                                continue  # Skip if still no valid set found
                        else:
                            logger.warning(f"No product URL found for '{original_set_name}'")
                            # self.skip_tracker.add(
                            #     site.get("name"),
                            #     locals().get("name", "<unknown>"),
                            #     f"No product URL found for: {set_name}",
                            #     data,
                            # )
                            continue

                    # logger.info(f"after get_closest_set_name form: {set_name} ")
                    set_code = await CardService.get_clean_set_code_from_set_name(set_name)
                    if not set_code:
                        # Attempt fallback using parts of data-name
                        name_parts = data.get("data-name", "").split(" - ")
                        for part in reversed(name_parts):  # Start from the most specific suffix
                            fallback_set_name = await CardService.get_closest_set_name(part.strip())
                            fallback_set_code = await CardService.get_clean_set_code_from_set_name(fallback_set_name)
                            if fallback_set_code:
                                logger.debug(
                                    f"Fallback set code found from data-name part '{part}': {fallback_set_name} ({fallback_set_code})"
                                )
                                set_code = fallback_set_code
                                set_name = fallback_set_name
                                break
                        if not set_code:
                            # logger.info(
                            #     f"[SET CODE] Skipping card after fallback {name} unknown set: {set_code} for site: {site.get('name')}\n {data}"
                            # )
                            # self.skip_tracker.add(
                            #     site.get("name"), name, f"Failed to resolve set code for: {set_name}", data
                            # )
                            continue
                    if set_code.lower() == "pbook":
                        # logger.info(
                        #     f"after pbook: {set_code} name:{set_name} for site: {site.get('name')}\n data: {data}\n {data}"
                        # )
                        # self.skip_tracker.add(
                        #     site.get("name"), name, f"Failed to resolve set code for: {set_name}", data
                        # )
                        continue
                    # logger.info(f"after get_clean_set_code form: {set_code} ")

                    test = data.get("data-variant", "").strip()
                    if not test:
                        # self.skip_tracker.add(
                        #     site.get("name"), locals().get("name", "<unknown>"), "Missing variant ID", data
                        # )
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
                        # self.skip_tracker.add(
                        #     site.get("name"), locals().get("name", "<unknown>"), "Missing variant ID", data
                        # )
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
                    logger.error(f"Error processing form in {site.get('name')}: {str(e)}", exc_info=True)
                    continue

        else:
            # Original scrapper strategy with enhanced validation
            content = soup.find(
                "div",
                {"class": ["content", "content clearfix", "content inner clearfix"]},
            )
            if content is None:
                logger.error(f"Content div not found for site {site.get('name')}")
                return pd.DataFrame()

            products_containers = content.find_all("div", {"class": "products-container browse"})
            if not products_containers:
                logger.warning(f"No variants container found for site {site.get('name')}")
                return pd.DataFrame()

            for container in products_containers:
                products = container.find_all("li", {"class": "product"})
                for product in products:
                    if not self.is_magic_card(product):
                        # self.skip_tracker.add(
                        #     site.get("name"), locals().get("name", "<unknown>"), "Non Magic card", data
                        # )
                        continue
                    variants_section = product.find("div", {"class": "variants"})
                    if not variants_section:
                        # self.skip_tracker.add(
                        #     site.get("name"), locals().get("name", "<unknown>"), "No variant could be found", data
                        # )
                        continue

                    for variant in variants_section.find_all("div", {"class": "variant-row"}):
                        if "no-stock" in variant.get("class", []):
                            # self.skip_tracker.add(
                            #     site.get("name"), locals().get("name", "<unknown>"), "No stocks found", data
                            # )
                            continue
                        try:
                            # Extract and validate quality and language
                            variant_data = variant.find(
                                "span",
                                {"class": "variant-short-info variant-description"},
                            ) or variant.find("span", {"class": "variant-short-info"})

                            if not variant_data:
                                # self.skip_tracker.add(
                                #     site.get("name"),
                                #     locals().get("name", "<unknown>"),
                                #     "No variant_data could be found",
                                #     data,
                                # )
                                continue
                            form_tag = variant.find("form", {"class": "add-to-cart-form"})
                            if not form_tag:
                                # self.skip_tracker.add(
                                #     site.get("name"),
                                #     locals().get("name", "<unknown>"),
                                #     "No form_Tag could be found",
                                #     data,
                                # )
                                continue
                            variant_id = form_tag.get("data-vid")
                            if not variant_id:
                                # self.skip_tracker.add(
                                #     site.get("name"),
                                #     locals().get("name", "<unknown>"),
                                #     "No variant_id could be found",
                                #     data,
                                # )
                                continue

                            # Get set name
                            meta_div = product.find("div", {"class": "meta"})
                            if not meta_div:
                                # self.skip_tracker.add(
                                #     site.get("name"),
                                #     locals().get("name", "<unknown>"),
                                #     "No meta_div could be found",
                                #     data,
                                # )
                                continue

                            # Get and validate name
                            name_header = meta_div.find("h4", {"class": "name"}) if meta_div else None
                            if not name_header:
                                # self.skip_tracker.add(
                                #     site.get("name"),
                                #     locals().get("name", "<unknown>"),
                                #     "No name header could be found",
                                #     data,
                                # )
                                continue

                            parsed_card = parse_card_string(name_header.text)
                            if not parsed_card:
                                # self.skip_tracker.add(
                                #     site.get("name"),
                                #     locals().get("name", "<unknown>"),
                                #     "Failed to parse card name",
                                #     data,
                                # )
                                continue

                            clean_name = clean_card_name(parsed_card.get("Name", name_header.text), card_names)
                            if not clean_name or (
                                clean_name not in card_names and clean_name.split(" // ")[0].strip() not in card_names
                            ):
                                # self.skip_tracker.add(
                                #     site.get("name"), locals().get("name", "<unknown>"), "Invalid card name", data
                                # )
                                continue

                            # Extract and validate quality and language
                            quality_language = normalize_variant_description(variant_data.text)
                            # logger.info(f"after normalize_variant_description: {quality_language}")
                            quality, language = extract_quality_language(quality_language)

                            if not quality or not language:
                                # self.skip_tracker.add(
                                #     site.get("name"), name, "Quality or language not found for variant", data
                                # )
                                continue

                            # Extract and validate quantity
                            quantity = extract_quantity(variant)
                            if quantity is None or quantity <= 0:
                                # self.skip_tracker.add(
                                #     site.get("name"),
                                #     locals().get("name", "<unknown>"),
                                #     "Invalid quantity for variant",
                                #     data,
                                # )
                                continue

                            # Extract and validate price
                            price = extract_price(variant)
                            if price is None or price <= 0:
                                # self.skip_tracker.add(
                                #     site.get("name"),
                                #     locals().get("name", "<unknown>"),
                                #     "Invalid price for variant",
                                #     data,
                                # )
                                continue

                            set_elem = meta_div.find("span", {"class": "category"}) if meta_div else None
                            if not set_elem:
                                # self.skip_tracker.add(
                                #     site.get("name"),
                                #     locals().get("name", "<unknown>"),
                                #     "Set element not found for variant",
                                #     data,
                                # )
                                continue

                            if any(cat in set_elem.text.lower() for cat in excluded_categories):
                                # self.skip_tracker.add(
                                #     site.get("name"), locals().get("name", "<unknown>"), "Excluded category found", data
                                # )
                                continue

                            set_name = await CardService.get_closest_set_name(set_elem.text.lower())
                            if not set_name:
                                # self.skip_tracker.add(
                                #     site.get("name"), name, "Failed to get set name for variant", data
                                # )
                                continue
                            set_code = await CardService.get_clean_set_code_from_set_name(set_name)
                            if not set_code:
                                # Attempt fallback using parts of data-name
                                name_parts = name_header.split(" - ")
                                for part in reversed(name_parts):  # Start from the most specific suffix
                                    fallback_set_name = await CardService.get_closest_set_name(part.strip())
                                    fallback_set_code = await CardService.get_clean_set_code_from_set_name(
                                        fallback_set_name
                                    )
                                    if fallback_set_code:
                                        logger.debug(
                                            f"Fallback set code found from data-name part '{part}': {fallback_set_name} ({fallback_set_code})"
                                        )
                                        set_code = fallback_set_code
                                        set_name = fallback_set_name
                                        break
                                if not set_code:
                                    # self.skip_tracker.add(
                                    #     site.get("name"), name, "Failed to get set code for variant", data
                                    # )
                                    continue

                            # Determine foil status and version
                            is_foil = parsed_card.get("Foil", False)
                            version = CardVersion.normalize(parsed_card.get("Version", "Standard"))
                            if not version:
                                # self.skip_tracker.add(
                                #     site.get("name"),
                                #     locals().get("name", "<unknown>"),
                                #     "Failed to get version for variant",
                                #     data,
                                # )
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

        # self.skip_tracker.log_all()
        if not cards:
            logger.warning(f"No valid cards found for {site.get('name')} ({total_variant} variants)")
            return pd.DataFrame()

        try:

            df = self.standardize_card_dataframe(cards)
            logger.debug(f"[CRYSTAL] Processed {len(df)} unique variants for {len(df['name'].unique())} distinct cards")
            return df

        except Exception as e:
            logger.error(f"Error creating DataFrame for {site.get('name')}: {str(e)}", exc_info=True)
            return pd.DataFrame()

    async def extract_info_f2f_json(self, json_data, site, card_names):
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
                        set_code = await CardService.get_clean_set_code_from_set_name(set_name)

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
                            test_code = await CardService.get_clean_set_code_from_set_name(set_name)
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

            df = self.standardize_card_dataframe(cards)
            logger.info(f"[SHOPIFY] Processed {len(df)} unique variants for {len(df['name'].unique())} distinct cards")
            return df
        except Exception as e:
            logger.error(
                f"Error processing Shopify JSON for {site.name}: {str(e)}",
                exc_info=True,
            )
            return pd.DataFrame()

    async def generate_search_payload_crystal(self, site_data, card_names):
        """Generate search payload for CrystalCommerce sites."""
        auth_token, relevant_headers = await SiteService.get_site_details_async(site_data)

        query_string = "\r\n".join(card_names)
        site_name = site_data["name"]
        if "orchardcitygames" in site_name.lower():
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

    async def _search_crystal_batch(self, site_data, batch_card_names, network):
        """
        Simplified crystal commerce search with better error handling.
        Works with site_data instead of a SQLAlchemy model.
        """
        max_retries = 3
        retry_count = 0
        backoff_factor = 1
        site_name = site_data["name"]
        site_url = site_data["url"]

        # Get site details including authentication token and headers
        search_url = site_url.rstrip("/")

        while retry_count < max_retries:
            try:
                retry_count += 1
                logger.debug(
                    f"Attempting batch search ({len(batch_card_names)}) for {site_name} (attempt {retry_count}/{max_retries})"
                )

                payload, request_headers = await self.generate_search_payload_crystal(site_data, batch_card_names)

                # Make the request with an increased timeout
                response = await network.post_request(search_url, payload, headers=request_headers, site=site_data)

                if not response:
                    logger.warning(f"Search request failed for {site_name} (attempt {retry_count}/{max_retries})")
                    await asyncio.sleep(backoff_factor * (2 ** (retry_count - 1)))
                    continue

                logger.debug(f"Successfully received response for batch from {site_name}")

                # Process the response to handle potential "Connection closed" issues
                try:
                    soup = BeautifulSoup(response, "html.parser")

                    # Check if we got a valid response by looking for product elements
                    products = soup.find_all(["li", "div"], {"class": ["product", "products-container"]})

                    if not products:
                        logger.warning(f"No product elements found in response from {site_name}")

                        # Try to extract any errors from the response
                        error_elements = soup.find_all(["div", "p"], {"class": ["error", "alert", "notice"]})
                        if error_elements:
                            for error in error_elements:
                                logger.warning(f"Error from {site_name}: {error.text.strip()}")

                    await asyncio.sleep(1.5)  # Add delay to avoid rate limiting
                    return soup

                except Exception as e:
                    logger.error(f"Error parsing response from {site_name}: {str(e)}")
                    await asyncio.sleep(backoff_factor * (2 ** (retry_count - 1)))
                    continue

            except Exception as e:
                logger.error(
                    f"Error in crystal commerce search for {site_name} (attempt {retry_count}/{max_retries}): {str(e)}",
                    exc_info=True,
                )
                await asyncio.sleep(backoff_factor * (2 ** (retry_count - 1)))
                continue

            backoff_factor *= 2

        logger.error(f"All {max_retries} attempts failed for batch search on {site_name}")
        return None

    async def search_crystalcommerce(self, site_data, card_names, network):
        """Search CrystalCommerce with batched requests for efficiency."""
        site_name = site_data["name"]
        BATCH_SIZE = 40  # Number of cards per request

        try:
            # Prepare search payload
            clean_names = [clean_card_name(name, card_names) for name in card_names if name]

            if not clean_names:
                logger.error(f"No valid card names to search for {site_name}")
                return None

            # Split the card list into chunks of BATCH_SIZE
            card_batches = [clean_names[i : i + BATCH_SIZE] for i in range(0, len(clean_names), BATCH_SIZE)]

            # Prepare tasks for all batches
            tasks = [self._search_crystal_batch(site_data, batch, network) for batch in card_batches]

            logger.info(f"Sending {len(card_batches)} batch of requests for {site_name}...")

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
                logger.error(f"All batches failed for {site_name}")
                return None

            logger.info(f"Successfully processed {len(valid_results)}/{len(card_batches)} batches for {site_name}")

            # Combine all soups into a single soup object (simple merge)
            combined_html = "<html><body>" + "".join([str(soup) for soup in valid_results]) + "</body></html>"
            combined_soup = BeautifulSoup(combined_html, "html.parser")

            return combined_soup

        except Exception as e:
            logger.error(
                f"Error in search_crystalcommerce for {site_name}: {str(e)}",
                exc_info=True,
            )
            return None

    async def search_f2f(self, site_data, card_names, network):
        """Submit search in smaller batches to handle large result sets."""
        site_name = site_data["name"]
        site_api_url = site_data["api_url"]

        _, headers = await SiteService.get_site_details_async(site_data)

        # Break into batches of 10 cards each
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
                site_api_url, batch_payload, headers=headers, site=site_data, use_json=True
            )

            if response_text is None:
                logger.warning(f"[F2F] No response for batch {batch_index+1}")
                continue

            try:
                batch_results = json.loads(response_text)
                batch_cards_found = batch_results.get("Cards", {})
                batch_card_count = len(batch_cards_found)

                # Log batch results
                # logger.info(f"[F2F] Batch {batch_index+1} found {batch_card_count} cards")

                if batch_card_count > 0:
                    # Log first few found cards for debugging
                    # found_cards = list(batch_cards_found.keys())
                    # logger.info(f"[F2F] Batch {batch_index+1} cards: {', '.join(found_cards[:5])}")

                    # Merge with overall results
                    all_results["Cards"].update(batch_cards_found)
                else:
                    # If no cards found, retry once with delay
                    # logger.info(f"[F2F] No cards in batch {batch_index+1}, retrying after delay")
                    await asyncio.sleep(3)

                    retry_response = await network.post_request(
                        site_api_url, batch_payload, headers=headers, site=site_data, use_json=True
                    )

                    if retry_response:
                        retry_results = json.loads(retry_response)
                        retry_cards = retry_results.get("Cards", {})
                        # logger.info(f"[F2F] Retry for batch {batch_index+1} found {len(retry_cards)} cards")
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
        # total_cards_found = len(all_results["Cards"])
        # logger.info(f"[F2F] Total cards found across all batches: {total_cards_found}/{len(card_names)}")

        # Check how many requested cards were found
        found_requested = set(all_results["Cards"].keys()).intersection(set(card_names))
        logger.info(f"[F2F] Found {len(found_requested)} of the {len(card_names)} requested cards")

        # Copy other fields from the last response to maintain response structure
        if "batch_results" in locals() and batch_results:
            for key in batch_results:
                if key != "Cards":
                    all_results[key] = batch_results[key]

        # missing_cards = set(card_names) - set(all_results["Cards"].keys())
        # if missing_cards:
        #     logger.warning(f"[F2F] The following {len(missing_cards)} cards were not found:")
        #     for missing in sorted(missing_cards):
        #         logger.warning(f"[F2F] Missing card: {missing}")

        return all_results

    async def search_shopify(self, site_data, card_names, network):
        """Get card data from Shopify via Binder API using site_data dict"""
        try:
            site_name = site_data["name"]
            logger.info(f"Searching Shopify: {site_name}")

            _, relevant_headers = await SiteService.get_site_details_async(site_data)
            api_url, json_payload = CardService.create_shopify_url_and_payload(site_data, card_names)

            # logger.info(f"Searching Shopify url and payload returned: {api_url}, {json_payload}")
            response = await network.post_request(api_url, json_payload, headers=relevant_headers, site=site_data)
            await asyncio.sleep(2)  # Add delay to avoid rate limiting

            if not response:
                logger.error(f"Failed to get response from Binder API for {site_name}")
                return None

            try:
                # logger.info(f"Returning JSON: {site_name}")
                return json.loads(response)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON response from {site_name}: {str(e)}", exc_info=True)
                return None

        except Exception as e:
            logger.error(f"Error searching Shopify site {site_name}: {str(e)}", exc_info=True)
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
