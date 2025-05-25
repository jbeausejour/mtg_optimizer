import logging
import re
from app.constants import CardLanguage, CardQuality
import unicodedata

logger = logging.getLogger(__name__)


def parse_card_string(card_string):
    try:
        card = {}
        parts = [part.strip() for part in card_string.split(" - ")]

        name = parts[0]
        version = foil = None

        if len(parts) > 1:
            for part in parts[1:]:
                if "foil" in part.lower() and "non-foil" not in part.lower():
                    foil = part
                else:
                    version = part
        card["Name"] = name
        card["Version"] = version
        card["Foil"] = foil

        return card

    except Exception as e:
        logger.error(f"Fatal error in parse_card_string: {str(e)}")
        return None


def clean_card_name(unclean_name, original_names):
    try:
        # Remove any numeric suffixes in parentheses
        without_suffixe_name = re.sub(r"\s*\(\d+\)", "", unclean_name)

        # ✅ Remove set names in parentheses
        cleaned_name = re.sub(r"\s*\(.*?\)", "", without_suffixe_name).strip()

        # Check if the name is in the original list without quotes
        if cleaned_name in original_names:
            return cleaned_name

        # Check if the name without outer quotes is in the original list
        name_without_outer_quotes = re.sub(r'^"|"$', "", cleaned_name)  # Remove only outer quotes
        if name_without_outer_quotes in original_names:
            return name_without_outer_quotes

        # ✅ Handle double-sided cards (e.g., "Blightstep Pathway // Searstep Pathway")
        if " // " in name_without_outer_quotes:
            front_side = name_without_outer_quotes.split(" // ")[0].strip()
            if front_side in original_names:
                return front_side

        # If the name is not in the original list, return as is
        return unclean_name

    except Exception as e:
        logger.error(f"Fatal error in clean_card_name: {str(e)}")
        return None


def extract_numbers(s):
    try:
        number_pattern = re.compile(r"\d+")
        match = number_pattern.search(s)
        if match:
            extracted_digits = match.group()
            return int(extracted_digits)
        else:
            return 0

    except Exception as e:
        logger.error(f"Fatal error in extract_numbers: {str(e)}")
        return None


def normalize_price(price_string):
    try:
        price_pattern = re.compile(r"(\d{1,3}(?:,\d{3})*\.\d{2})")
        match = price_pattern.search(price_string)
        if match:
            price = match.group(1)
            return round(float(price.replace(",", "")), 2)
        else:
            return 0.0
    except Exception as e:
        logger.error(f"Fatal error in normalize_price: {str(e)}")
        return None


def detect_foil(product_foil=None, product_version=None, variant_data=None):
    try:
        if not any([product_foil, product_version, variant_data]):
            return False
        check_strings = [s.lower() for s in [product_foil, product_version, variant_data] if s is not None]
        return any("foil" in s for s in check_strings)
    except Exception as e:
        logger.exception(f"Error in detect_foil {str(e)}")
        return None


def extract_price(variant):
    try:
        price_elem = (
            variant.find("span", {"class": "regular price"})
            or variant.find("span", {"class": "price"})
            or variant.find("span", {"class": "variant-price"})
        )
        if not price_elem:
            return None
        price_value = normalize_price(price_elem.text.strip())
        return price_value if price_value and price_value > 0 else None
    except Exception as e:
        logger.error(f"Error extracting price: {str(e)}")
        return None


def extract_quantity(variant):
    try:
        qty_elem = (
            variant.find("span", {"class": "variant-short-info variant-qty"})
            or variant.find("span", {"class": "variant-short-info"})
            or variant.find("span", {"class": "variant-qty"})
            or variant.find("input", {"class": "qty", "type": "number"})
        )
        if not qty_elem:
            return None
        if qty_elem.name == "input":
            qty = qty_elem.get("max") or qty_elem.get("value")
            return int(qty) if qty and int(qty) > 0 else None
        qty_text = qty_elem.text.strip()
        return extract_numbers(qty_text) or None
    except Exception as e:
        logger.error(f"Error in extract_quantity: {str(e)}")
        return None


def extract_quality_language(quality_language):
    try:
        if not quality_language:
            return "DMG", "Unknown"
        if isinstance(quality_language, list):
            quality_language = ", ".join(str(x) for x in quality_language)
        variant_parts = quality_language.split(",")
        raw_quality = variant_parts[0].strip() if len(variant_parts) >= 1 else "DMG"
        raw_language = variant_parts[1].strip() if len(variant_parts) >= 2 else "Unknown"
        quality = CardQuality.normalize(raw_quality)
        language = CardLanguage.normalize(raw_language)
        return quality, language
    except Exception as e:
        logger.error(f"Error in extract_quality_language: {str(e)}")
        return "DMG", "Unknown"


def find_name_version_foil(place_holder):
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
                version_part = re.sub(r"\bfoil\b", "", item, flags=re.IGNORECASE).strip()
                if version_part:
                    product_version = version_part
            elif item:
                product_version = item
        return product_name, product_version, product_foil
    except Exception as e:
        logger.error(f"Error in find_name_version_foil: {str(e)}")
        return None


def parse_shopify_variant_title(title):
    try:
        set_match = re.search(r"\[(.*?)\]", title)
        if not set_match:
            return None
        set_name = set_match.group(1).strip()
        remaining = title.split("]")[-1].strip()
        is_foil = "Foil" in remaining
        quality = remaining.replace("Foil", "").strip()
        return set_name, quality, is_foil
    except Exception as e:
        logger.error(f"Error parsing shopify variant title: {str(e)}")
        return None


def normalize_variant_description(variant_description):
    try:
        cleaned_description = variant_description.split(":")[-1].strip()
        return [part.strip() for part in cleaned_description.split(",")]
    except Exception as e:
        logger.error(f"Error normalizing variant description: {str(e)}")
        return None


def normalize_string(name: str) -> str:
    return unicodedata.normalize("NFKC", name)
