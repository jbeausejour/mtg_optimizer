import re
import time
import traceback
from ast import Continue
from typing import Container
from urllib.parse import quote_plus, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup
from mtg_card import Card
from mtg_logger import *

STRATEGY_ADD_TO_CART = 1
STRATEGY_SCRAPPER = 2
STRATEGY_HAWK = 3
strats = {
    STRATEGY_ADD_TO_CART: "Add-To-Cart",
    STRATEGY_SCRAPPER: "Scrapper",
    STRATEGY_HAWK: "Hawk",
}

logger = None


def set_scrapper_logger(new_logger):
    global logger
    logger = new_logger


def clean_card_name(name, original_names):
    name = re.sub(r"\s*\(\d+\)", "", name)
    if name in original_names:
        return name
    name_without_outer_quotes = re.sub(r'^"|"$', "", name)
    if name_without_outer_quotes in original_names:
        return name_without_outer_quotes
    return name


def extract_domain(url):
    domain_pattern = re.compile(
        r"^(?:https?:\/\/)?(?:[^@\n]+@)?(?:www\.)?([^:\/\n?]+)(.com)"
    )
    match = domain_pattern.search(url)
    if match:
        domain = match.group(1)
        domain = domain.split(".crystalcommerce")[0]
        return domain
    return url


def extract_info(soup, site, card_names, strategy):
    if soup is None:
        logger.info(
            color_msg(
                [
                    ("[Warning] ", "d_yellow"),
                    (str(site), "b_cyan"),
                    (f"Soup is ", "rst"),
                    (" None!", "d_red"),
                    (" in extract_info (ei).", "rst"),
                ]
            )
        )
        return pd.DataFrame()
    cards = []
    seen_variants = set()
    substrings_to_check = [
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
    ]
    if strategy == STRATEGY_HAWK:
        cards = strategy_hawk(soup)
        card_dicts = [card.to_dict() for card in cards]
        return pd.DataFrame(card_dicts)
    top_level = ["content", "content clearfix", "content inner clearfix"]
    for x in top_level:
        content = soup.find("div", {"class": x})
        if content is None:
            logger.info(
                color_msg(
                    [
                        ("[Warning] ", "d_yellow"),
                        (str(site), "b_cyan"),
                        (f" class': {x}", "rst"),
                        (" NOT found", "d_red"),
                        (" in extract_info (ei).", "rst"),
                    ]
                )
            )
        else:
            break
    if content is None:
        logger.error(
            color_msg(
                [
                    ("[ERROR] ", "d_red"),
                    (str(site), "b_cyan"),
                    (" All classes: 'content'", "rst"),
                    (" NOT found", "d_red"),
                ]
            )
        )
        if soup.find("title"):
            logger.error(
                color_msg(
                    [
                        ("[Error] ", "d_red"),
                        ("Site returned error: ", "rst"),
                        (str(soup.find("title").text), "b_cyan"),
                    ]
                )
            )
            print(soup)
        return pd.DataFrame()
    products_containers = content.find_all(
        "div", {"class": "products-container browse"}
    )
    if products_containers is None:
        logger.warning(
            color_msg(
                [
                    (str(site), "b_cyan"),
                    (" Warning:", "d_yellow"),
                    (" class': 'products-container browse", "rst"),
                    (" NOT found", "d_red"),
                    (" in extract_info (ei).", "rst"),
                ]
            )
        )
        return pd.DataFrame()
    for products_container in products_containers:
        ul_element = products_container.find("ul", {"class": "products"})
        list_items = ul_element.find_all("li", {"class": "product"})
        for item in list_items:
            image = item.find("div", {"class": "image"})
            a_tag = image.find("a", href=True)
            if a_tag and "yugioh" in a_tag["href"]:
                value = a_tag["href"]
                logger.debug(
                    color_msg(
                        [
                            (str(site), "b_cyan"),
                            (" Error: ", "d_red"),
                            ("Card isn't a magic_single: ", "rst"),
                            (str(value), "rst"),
                        ]
                    )
                )
                continue
            meta = item.find("div", {"class": "meta"})
            test_category = meta.find(
                "span", {"class": "category"}).text.strip()
            test_title = meta.find("h4", {"class": "name"}).text.strip()
            if test_title:
                card = parse_card_string(test_title)
                card.Site = site
            else:
                card = Card()
                card.Name = test_title
                card.Site = site
            logger.debug(
                color_msg(
                    [
                        ("[Warning] ", "b_magenta"),
                        (" before clean:", "d_red"),
                        (str(card.Name), "b_cyan"),
                    ]
                )
            )
            card.Name = clean_card_name(card.Name, card_names)
            logger.debug(
                color_msg(
                    [
                        ("[Warning] ", "b_magenta"),
                        (" after clean:", "d_red"),
                        (str(card.Name), "b_cyan"),
                    ]
                )
            )
            if not card.Name:
                logger.error(
                    color_msg(
                        [
                            ("[ERROR] ", "d_red"),
                            (str(site), "b_cyan"),
                            ("Cant find card_name in h4: ", "rst"),
                            (card.Name, "b_cyan"),
                        ]
                    )
                )
            if (card.Name not in card_names) and (
                card.Name.split(" // ")[0].strip() not in card_names
            ):
                msg = color_msg(
                    [
                        (str(site), "b_cyan"),
                        (" Debug:", "d_cyan"),
                        (" Card [", "rst"),
                        (str(card.Name), "b_yellow"),
                        ("] NOT found", "d_red"),
                        (" in initial list (ei).", "rst"),
                    ]
                )
                logger.debug(msg)
                continue
            if any(
                substring in test_category.lower() for substring in substrings_to_check
            ):
                logger.debug(
                    color_msg(
                        [
                            (str(site), "b_cyan"),
                            (" INFO: [", "d_yellow"),
                            (str(card.Name), "rst"),
                            ("]: is in category ", "rst"),
                            (str(test_category), "d_cyan"),
                        ]
                    )
                )
                continue
            card.Edition = test_category
            variants = item.find("div", {"class": "variants"})
            variant_rows = variants.find_all("div", {"class": "variant-row"})
            for variant in variant_rows:
                if strategy == 1:
                    card_variant = strategy_add_to_cart(card, variant)
                elif strategy == 2:
                    card_variant = strategy_scrapper(card, variant)
                if card_variant is not None and card_variant not in seen_variants:
                    cards.append(card_variant)
                    seen_variants.add(card_variant)
    card_dicts = [card.to_dict() for card in cards]
    return pd.DataFrame(card_dicts)


def extract_numbers(s):
    number_pattern = re.compile(r"\d+")
    match = number_pattern.search(s)
    if match:
        extracted_digits = match.group()
    else:
        extracted_digits = "0"
    try:
        return int(extracted_digits)
    except ValueError:
        return 0


def extract_price(card, variant):
    price_elem = variant.find("span", {"class": "regular price"})
    if price_elem is not None:
        price_text = price_elem.text
        return normalize_price(price_text)
    else:
        logger.error(
            color_msg(
                [
                    (str(card.Site), "b_cyan"),
                    (
                        f": in Fct:strategy_scrapper, Price element not found!... ",
                        "rst",
                    ),
                    (str(card.Name), "d_red"),
                    (f"Problematic variant: {variant}", "rst"),
                ]
            )
        )
        return 0.0


def extract_quality_language(card, variant):
    variant_description = variant.find(
        "span", {"class": "variant-short-info variant-description"}
    ) or variant.find("span", {"class": "variant-short-info"})
    if variant_description:
        quality_language = normalize_variant_description(
            variant_description.text)
        logger.debug(
            color_msg(
                [
                    (str(card.Site), "b_cyan"),
                    (" [INFO]", "b_yellow"),
                    (" Results of variant-description is: [", "rst"),
                    (str(quality_language), "b_yellow"),
                    ("].", "rst"),
                ]
            )
        )
        return quality_language[:2]
    else:
        logger.error(
            color_msg(
                [
                    (str(card.Site), "b_cyan"),
                    (
                        ": in extract_quality_language can't find variant-description ",
                        "rst",
                    ),
                    (str(card.Name), "d_red"),
                    (f"Problematic variant: {variant}", "rst"),
                ]
            )
        )
        return None


def extract_quantity(card, variant):
    variant_qty = variant.find(
        "span", {"class": "variant-short-info variant-qty"}
    ) or variant.find("span", {"class": "variant-short-info"})
    if variant_qty:
        variant_qty = variant_qty.text.strip()
        logger.debug(
            color_msg(
                [
                    (str(card.Site), "b_cyan"),
                    (" [INFO]", "b_yellow"),
                    (" Results of variant-qty is: [", "rst"),
                    (str(variant_qty), "b_yellow"),
                    ("].", "rst"),
                ]
            )
        )
        return extract_numbers(variant_qty)
    else:
        logger.error(
            color_msg(
                [
                    (str(card.Site), "b_cyan"),
                    (": in extract_quantity can't find variant-qty ", "rst"),
                    (str(card.Name), "d_red"),
                    (f"Problematic variant: {variant}", "rst"),
                ]
            )
        )
        return None


def extract_single_float(s):
    matches = re.findall(r"\b\d+\.?\d*\b", s)
    if matches:
        return round(matches[0], 2)
    else:
        return None


def fetch_url(domain, url, retries=3, backoff_factor=1):
    for attempt in range(retries):
        response = requests.get(url)
        if response.status_code != 200:
            sleep_time = backoff_factor * (2**attempt)
            logger.info(
                color_msg(
                    [
                        ("[INFO] ", "d_yellow"),
                        (str(domain), "b_cyan"),
                        (f" {response.status_code}", "b_yellow"),
                        (" ERROR detected on GET. Retrying in ", "rst"),
                        (f"{sleep_time}", "b_cyan"),
                        (" seconds...", "rst"),
                    ]
                )
            )
            time.sleep(sleep_time)
            continue
        return response
    return None


def find_name_version_foil(place_holder):
    product_name = ""
    product_version = ""
    product_foil = ""
    items = re.split(r" - ", place_holder)
    items = [x.strip() for x in items]
    product_name = items[0]
    for item in items[1:]:
        if "Foil" in item:
            product_foil = item
        else:
            product_version = item
    logger.debug(
        color_msg(
            [
                ("[INFO]", "d_yellow"),
                (" Card [", "rst"),
                (str(place_holder), "b_yellow"),
                ("] values are:", "rst"),
            ]
        )
    )
    logger.debug(
        color_msg(
            [
                ("   product_name: [", "rst"),
                (str(product_name), "b_blue"),
                ("].", "rst"),
            ]
        )
    )
    logger.debug(
        color_msg(
            [
                ("   product_version: [", "rst"),
                (str(product_version), "b_blue"),
                ("].", "rst"),
            ]
        )
    )
    logger.debug(
        color_msg(
            [
                ("   product_foil: [", "rst"),
                (str(product_foil), "b_blue"),
                ("].", "rst"),
            ]
        )
    )
    return product_name, product_version, product_foil


def normalize_price(price_string):
    price_pattern = re.compile(r"(\d{1,3}(?:,\d{3})*\.\d{2})")
    match = price_pattern.search(price_string)
    if match:
        price = match.group(1)
        return round(float(price.replace(",", "")), 2)
    else:
        logger.error(
            color_msg(
                [
                    ("[ERROR] ", "d_red"),
                    ("In extract_price function: problematic price: ", "rst"),
                    (str(price_string), "d_red"),
                ]
            )
        )
        return 0.0


def normalize_variant_description(variant_description):
    cleaned_description = variant_description.split(":")[-1].strip()
    variant_parts = cleaned_description.split(",")
    variant_parts = [part.strip() for part in variant_parts]
    return variant_parts


def parse_card_string(card_string):
    card = Card()
    parts = [part.strip() for part in card_string.split(" - ")]
    name = parts[0]
    version = foil = special = None
    if len(parts) > 1:
        for part in parts[1:]:
            if "foil" in part.lower() and "non-foil" not in part.lower():
                foil = part
            elif part.isdigit() or "(" in part and ")" in part:
                special = part
            else:
                version = part
    card.Name = name
    card.Version = version
    card.Foil = foil
    return card


def post_request(domain, url, headers, payload, retries=3, backoff_factor=1):
    for attempt in range(retries):
        response = requests.post(url, headers=headers, data=payload)
        if response.status_code != 200:
            sleep_time = backoff_factor * (2**attempt)
            logger.info(
                color_msg(
                    [
                        ("[INFO] ", "b_yellow"),
                        (str(domain), "b_cyan"),
                        (f" {response.status_code}", "b_yellow"),
                        (" ERROR detected on POST. Retrying in ", "rst"),
                        (f"{sleep_time}", "b_cyan"),
                        (" seconds...", "rst"),
                    ]
                )
            )
            time.sleep(sleep_time)
            continue
        return response
    return None


def process_sites(site, card_names, strategy):
    cards_df = None
    domain = extract_domain(site)
    soup = search_crystalcommerce(domain, site, card_names)
    if not soup:
        return None
    try:
        mixed_message = color_msg(
            [
                ("Extracting for site: ", "rst"),
                (str(domain), "d_cyan"),
                (f" ...", "rst"),
            ]
        )
        mixed_msg_pad(mixed_message)
        temp = strats[strategy]
        mixed_message = color_msg(
            [("Using stratey: ", "rst"), (str(temp), "d_cyan"), (".", "rst")]
        )
        mixed_msg_pad(mixed_message)
        cards_df = extract_info(soup, domain, card_names, strategy)
        if cards_df is None or cards_df.empty:
            logger.error(
                color_msg(
                    [
                        (str(domain), "b_cyan"),
                        (" Error: ", "d_red"),
                        (f"No cards were found using {strats[strategy]}", "rst"),
                    ]
                )
            )
            strategy = (
                STRATEGY_SCRAPPER
                if strategy == STRATEGY_ADD_TO_CART
                else STRATEGY_ADD_TO_CART
            )
            logger.info(
                color_msg(
                    [
                        (str(domain), "b_cyan"),
                        (f" Switching to {strats[strategy]} method... ", "b_red"),
                    ]
                )
            )
            cards_df = extract_info(soup, domain, card_names, strategy)
    except Exception as e:
        logger.exception("An error occurred")
        stack_trace = traceback.format_exc()
        logger.error(
            color_msg([("General exception. ", "d_red"),
                      ("continuing ...", "rst")])
        )
        logger.error(
            color_msg([("Exception detail: \n", "d_red"), (stack_trace, "rst")])
        )
        return pd.DataFrame()
    return cards_df


def search_crystalcommerce(domain, site_url, card_names):
    search_url = f"{site_url}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36",
        "Referer": site_url,
    }
    try:
        response = fetch_url(domain, search_url)
        if response is None:
            logger.error(
                color_msg(
                    [
                        ("[ERROR] ", "b_red"),
                        (str(domain), "b_cyan"),
                        (" Request error: ", "d_cyan"),
                        ("Failed to fetch response after retries", "rst"),
                    ]
                )
            )
            return None
        if response.content:
            soup = BeautifulSoup(response.content, "html.parser")
            auth_token_elem = soup.find(
                "input", {"name": "authenticity_token"})
            if not auth_token_elem:
                logger.info(
                    color_msg(
                        [
                            ("[INFO] ", "b_yellow"),
                            (str(domain), "b_cyan"),
                            (" Authentication token not found", "rst"),
                        ]
                    )
                )
            auth_token = auth_token_elem["value"]
            cards_payload = "\r\n".join(card_names)
            payload = {
                "authenticity_token": auth_token,
                "query": cards_payload,
                "submit": "Continue",
            }
            response = post_request(domain, search_url, headers, payload)
            if response:
                soup = BeautifulSoup(response.content, "html.parser")
                return soup
            else:
                logger.error(
                    color_msg(
                        [
                            ("[ERROR] ", "b_red"),
                            (str(domain), "b_cyan"),
                            (" Post Request error: ", "rst"),
                            ("Failed to post request after retries", "rst"),
                        ]
                    )
                )
                return None
    except requests.exceptions.RequestException as e:
        logger.error(
            color_msg(
                [
                    ("[ERROR] ", "b_red"),
                    ("Request error: ", "rst"),
                    (str(domain), "b_cyan"),
                    (str(e), "rst"),
                ]
            )
        )
        return None


def strategy_add_to_cart(card, variant):
    try:
        if "no-stock" in variant.get("class", []) or "0 In Stock" in variant:
            return None
        form_element = variant.find("form", {"class": "add-to-cart-form"})
        if not form_element:
            return None
        attributes = form_element.attrs
        if "data-name" not in attributes:
            return None
        unclean_name, product_version, product_foil = find_name_version_foil(
            attributes["data-name"]
        )
        if not card.Foil:
            card.Foil = product_foil
        if not card.Edition:
            card.Edition = product_version
        product_name = re.sub(r"\s*\(\d+\)$", "", unclean_name)
        for key, value in attributes.items():
            logger.debug(
                color_msg(
                    [(str(key), "b_green"), (" = ", "rst"), (str(value), "b_blue")]
                )
            )
        quality_language = normalize_variant_description(
            attributes["data-variant"])
        quality, language = quality_language[:2]
        logger.debug(
            color_msg(
                [
                    ("In Fct: strategy_add_to_cart. Results are: ", "rst"),
                    (f"{str(quality_language)}", "d_green"),
                ]
            )
        )
        select_tag = variant.find("select", {"class": "qty"}) or variant.find(
            "input", {"class": "qty"}
        )
        qty_available_element = (
            select_tag["max"] if select_tag and "max" in select_tag.attrs else None
        )
        if qty_available_element:
            if hasattr(qty_available_element, "text"):
                qty_available = qty_available_element.text.strip()
            else:
                qty_available = qty_available_element
        else:
            logger.error(
                color_msg(
                    [
                        ("[ERROR] ", "d_red"),
                        (
                            f"{card.Site}: in extract_qty_available, no quantity found ",
                            "rst",
                        ),
                        (str(qty_available_element), "d_red"),
                        (f" Problematic variant:  {variant}", "rst"),
                    ]
                )
            )
            qty_available = "0"
        card.Quality = quality
        card.Language = language
        card.Quantity = int(qty_available)
        card.Edition = attributes["data-category"]
        price = attributes["data-price"]
        card.Price = normalize_price(price)
        return card
    except Exception as e:
        logger.exception(color_msg([("An error occurred", "d_red")]))
        logger.error(
            color_msg(
                [
                    (
                        f"{card.Site}: in strategy_add_to_cart general Exception: {e}",
                        "rst",
                    ),
                    (str(product_name), "d_red"),
                    (f"Problematic variant: {variant}", "rst"),
                ]
            )
        )
        return None


def strategy_hawk(variant):
    cards_data = []
    for card_div in variant.select(".hawk-results__item"):
        card_details = {
            "name": card_div.select_one(".hawk-results__hawk-contentTitle").get_text(
                strip=True
            ),
            "image_url": card_div.select_one(".hawk-results__item-image img")["src"],
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
    for card in cards_data:
        print(card)
    return cards_data


def strategy_scrapper(card, variant):
    if "no-stock" in variant.get("class", []) or "0 In Stock" in variant:
        return None
    try:
        card.Quality, card.Language = extract_quality_language(card, variant)
        if card.Quality is None or card.Language is None:
            return None
        card.Quantity = extract_quantity(card, variant)
        if card.Quantity is None:
            return None
        card.Price = extract_price(card, variant)
    except Exception as e:
        logger.exception("An error occurred")
        logger.error(
            color_msg(
                [
                    (str(card.Site), "b_cyan"),
                    (
                        f": in Fct:strategy_scrapper, {type(e).__name__}. Problematic variant: {variant}",
                        "rst",
                    ),
                ]
            )
        )
        return None
    return card
