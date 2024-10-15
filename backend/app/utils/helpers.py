import re


def parse_card_string(card_string):
    # Removed MarketplaceCard, using simple dictionary to handle card info
    card = {}
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
    card["Name"] = name
    card["Version"] = version
    card["Foil"] = foil

    return card