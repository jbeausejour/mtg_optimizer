import re
from app.models.card import MarketplaceCard

def parse_card_string(card_string):
    card = {}
    parts = [part.strip() for part in card_string.split(' - ')]

    # Initialize variables for different parts
    name = parts[0]
    version = foil = special = None

    if len(parts) > 1:
        for part in parts[1:]:
            if 'foil' in part.lower() and 'non-foil' not in part.lower():
                foil = part
            elif part.isdigit() or '(' in part and ')' in part:
                special = part
            else:
                version = part
    card['name'] = name
    card['version'] = version
    card['foil'] = foil

    return card

def clean_card_name(name, original_names):
    # Remove any numeric suffixes in parentheses
    name = re.sub(r"\s*\(\d+\)", "", name)

    # Check if the name is in the original list without quotes
    if name in original_names:
        return name

    # Check if the name without outer quotes is in the original list
    name_without_outer_quotes = re.sub(r'^"|"$', '', name)  # Remove only outer quotes
    if name_without_outer_quotes in original_names:
        return name_without_outer_quotes

    # If the name is not in the original list, return as is
    return name

def extract_numbers(s):
    number_pattern = re.compile(r'\d+')
    match = number_pattern.search(s)
    if match:
        extracted_digits = match.group()
        return int(extracted_digits)
    else:
        return 0
    
def normalize_price(price_string):
    price_pattern = re.compile(r"(\d{1,3}(?:,\d{3})*\.\d{2})")
    match = price_pattern.search(price_string)
    if match:
        price = match.group(1)
        return round(float(price.replace(",", "")), 2)
    else:
        return 0.0