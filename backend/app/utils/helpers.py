import json
import logging
import re
import uuid

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

def clean_card_name(name, original_names):
    try:
        # Remove any numeric suffixes in parentheses
        name = re.sub(r"\s*\(\d+\)", "", name)

        # Check if the name is in the original list without quotes
        if name in original_names:
            return name

        # Check if the name without outer quotes is in the original list
        name_without_outer_quotes = re.sub(
            r'^"|"$', "", name)  # Remove only outer quotes
        if name_without_outer_quotes in original_names:
            return name_without_outer_quotes

        # If the name is not in the original list, return as is
        return name
    
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
    
