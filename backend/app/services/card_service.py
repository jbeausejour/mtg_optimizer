import json
import logging
import re
import functools
import uuid
from contextlib import contextmanager
from datetime import datetime

import redis
import requests
from app.constants.card_mappings import CardLanguage, CardVersion
from app.extensions import db
from app.models.buylist import UserBuylist
from app.models.UserBuylistCard import UserBuylistCard
from app.services.site_service import SiteService
from flask import current_app
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql import func
from thefuzz import fuzz, process

logger = logging.getLogger(__name__)

SCRYFALL_API_BASE = "https://api.scryfall.com"
SCRYFALL_CATALOG_CARD_NAMES = f"{SCRYFALL_API_BASE}/catalog/card-names"
SCRYFALL_SETS_URL = f"{SCRYFALL_API_BASE}/sets"

SCRYFALL_API_NAMED_URL = f"{SCRYFALL_API_BASE}/cards/named"
SCRYFALL_API_SEARCH_URL = f"{SCRYFALL_API_BASE}/cards/search"
CARDCONDUIT_URL = "https://cardconduit.com/buylist"

REDIS_HOST = "192.168.68.15"
REDIS_PORT = 6379
CACHE_EXPIRATION = 86400  # 24 hours (same as card names)
REDIS_SETS_KEY = "scryfall_set_codes"
REDIS_CARDNAME_KEY = "scryfall_card_names"


class CardService:

    # Promo mappings for known catalog references or special sets
    promo_mappings = {
        "dmu extras": "Dominaria United",
        "ikoria: extras": "Ikoria: Lair of Behemoths",
        "znr extras": "zendikar rising",
        "znr: extras": "Zendikar Rising",
        "bro extras": "The Brothers' War",
        "brothers' war extras": "The Brothers' War",
        "brothers war extras": "The Brothers' War",
        "mkm singles": "Murders at Karlov Manor",
        "mkm": "Murders at Karlov Manor",
        "afr extras": "Adventures in the Forgotten Realms",
        "#045 - duel decks m14/m63/m64": "Duel Decks: Zendikar vs. Eldrazi",
        "duel decks m14/m63/m64": "Duel Decks: Zendikar vs. Eldrazi",
        "cbl bundle promo": "Commander Legends: Battle for Baldur's Gate",
        "treasure chest promo": "Treasure Chest",
        "promos: miscellaneous": "Judge Gift Cards",
        "brawl deck exclusive": "Commander Collection",
        "brawl": "Commander Collection",
        "the list": "Mystery Booster: The List",
        "set boosters reserved list": "Mystery Booster: The List",
    }

    @contextmanager
    def transaction_context():
        """Context manager for database transactions"""
        session = db.session  # Ensure the session is explicitly retrieved
        try:
            yield session
            session.commit()
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Database error: {str(e)}")
            raise
        except Exception as e:
            session.rollback()
            logger.error(f"Error in transaction: {str(e)}")
            raise
        finally:
            session.close()

    """Handles card-related operations including validation and buylist management."""

    @staticmethod
    def get_redis_client():
        """Returns a Redis client instance."""
        return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)

    # ====== 🔹 Caching Scryfall Card Names 🔹 ======
    @staticmethod
    def fetch_scryfall_card_names():
        """Fetch the full list of valid card names from Scryfall and cache it in Redis with normalization."""
        redis_client = CardService.get_redis_client()

        try:
            logger.info("Fetching full card list from Scryfall...")
            response = requests.get("https://api.scryfall.com/catalog/card-names")
            response.raise_for_status()
            card_names = response.json().get("data", [])

            # ✅ Normalize all card names
            normalized_card_names = set()

            logger.info("Normalizing...")
            for name in card_names:
                normalized_name = name.strip().lower()
                normalized_card_names.add(normalized_name)

                # ✅ Handle double-sided cards
                if " // " in normalized_name:
                    parts = normalized_name.split(" // ")
                    normalized_card_names.add(parts[0])  # First part
                    normalized_card_names.add(parts[1])  # Second part

            # ✅ Store in Redis (convert set to list)
            logger.info("Storing full card list in redis...")
            redis_client.set(REDIS_CARDNAME_KEY, json.dumps(list(normalized_card_names)))

            logger.info(f"Cached {len(normalized_card_names)} card names from Scryfall.")
            return normalized_card_names

        except requests.RequestException as e:
            logger.error(f"Error fetching Scryfall card names: {str(e)}")
            return []

    @staticmethod
    def is_valid_card_name(card_name):
        """Check if a given card name exists in the cached Scryfall card list, handling double-sided names."""
        redis_client = CardService.get_redis_client()
        card_names = redis_client.get(REDIS_CARDNAME_KEY)

        if not card_names:
            card_names = CardService.fetch_scryfall_card_names()
        else:
            card_names = json.loads(card_names)

        # Normalize input (remove extra spaces, handle case sensitivity)
        normalized_input = card_name.strip().lower()

        # Direct match first
        if normalized_input in card_names:
            return True

        # Handle double-sided names (Scryfall uses " // ")
        for full_card_name in card_names:
            if " // " in full_card_name:
                # Extract both sides of the double-sided card
                sides = full_card_name.lower().split(" // ")
                if normalized_input in sides:
                    return True

        return False  # No match found

    @staticmethod
    def fetch_scryfall_set_codes():
        """Fetch all valid set codes from Scryfall and cache them in Redis, excluding certain sets."""
        redis_client = CardService.get_redis_client()
        cached_data = redis_client.get(REDIS_SETS_KEY)

        if cached_data:
            return json.loads(cached_data)

        try:
            logger.info("Fetching full set list from Scryfall...")
            response = requests.get(SCRYFALL_SETS_URL, timeout=10)
            response.raise_for_status()
            data = response.json()

            if not isinstance(data, dict) or "data" not in data:
                raise ValueError("Invalid response format from Scryfall API")

            sets_data = {}
            excluded_set_types = {
                "minigame",
                "alchemy",
                "memorabilia",
                "treasure_chest",
            }

            for set_data in data["data"]:
                if set_data["set_type"] in excluded_set_types:
                    continue

                set_name = set_data["name"].lower()
                sets_data[set_name] = {
                    "code": set_data["code"],
                    "name": set_data["name"],
                    "released_at": set_data.get("released_at", None),
                    "set_type": set_data["set_type"],
                }

            if sets_data:
                redis_client.setex(REDIS_SETS_KEY, CACHE_EXPIRATION, json.dumps(sets_data))
                logger.info(f"Cached {len(sets_data)} valid set codes from Scryfall.")
                return sets_data
            else:
                logger.warning("No valid set codes found from Scryfall API.")
                return {}

        except requests.RequestException as e:
            logger.error(f"Error fetching Scryfall set codes: {str(e)}")
            return {}

    # @staticmethod
    # def is_valid_set_name(set_name):
    #     """Check if a given set name exists in the cached Scryfall set list."""
    #     redis_client = CardService.get_redis_client()
    #     set_codes = redis_client.get(REDIS_SETS_KEY)

    #     if not set_codes:
    #         set_codes = CardService.fetch_scryfall_set_codes()
    #     else:
    #         set_codes = json.loads(set_codes)

    #     return set_name.lower() in set_codes

    # Set Operations
    @staticmethod
    def get_sets_data(force_refresh=False):
        """Fetch set data from Redis or refresh if needed."""
        redis_client = CardService.get_redis_client()

        if force_refresh:
            return CardService.fetch_scryfall_set_codes()

        cached_sets = redis_client.get(REDIS_SETS_KEY)
        if cached_sets:
            return json.loads(cached_sets)

        return CardService.fetch_scryfall_set_codes()  # Refresh if missing

    @staticmethod
    def fetch_all_sets():
        """Fetch all valid sets from Redis (cached from Scryfall)."""
        redis_client = CardService.get_redis_client()
        cached_sets = redis_client.get(REDIS_SETS_KEY)

        if cached_sets:
            return [{"set": code, "name": name} for name, code in json.loads(cached_sets).items()]

        return []

    @classmethod
    @functools.lru_cache(maxsize=1000)
    def _normalize_set_name(cls, name):
        """Robustly normalize set name to ensure accurate matching."""
        if not name:
            return []

        results = set()

        name_lower = name.lower().strip()
        results.add(name_lower)

        patterns_to_clean = [
            (r"#\d+\s*-\s*", ""),
            (r"\(\d+\)", ""),
            (r"[/:,-]", " "),
            (r"\s+m\d+\s*$", ""),
            (r"\s+", " "),
        ]

        cleaned_name = name_lower
        for pattern, replacement in patterns_to_clean:
            cleaned_name = re.sub(pattern, replacement, cleaned_name).strip()
        results.add(cleaned_name)

        prefixes = [
            "promo pack",
            "promotional",
            "promo packs",
            "commander",
            "token",
            "tokens",
            "minigame",
            "minigames",
            "art series",
            "art cards",
            "promos",
            "extras",
            "extra",
            "box set",
            "game day",
            "prerelease",
            "release",
            "buy a box",
            "bundle",
            "media insert",
            "universes beyond",
            "universe beyond",
            "non foil",
            "foil",
            "mps",
            "judge rewards",
            "unique & misc",
            "modern event deck",
            "extended art",
            "commander universes beyond",
        ]
        prefix_found = True
        while prefix_found:
            prefix_found = False
            for prefix in prefixes:
                if cleaned_name.startswith(prefix):
                    cleaned_name = cleaned_name[len(prefix) :].strip()
                    prefix_found = True
        results.add(cleaned_name)

        simplified_variants = [
            cleaned_name.replace(" ", ""),
            cleaned_name.replace("'", ""),
            cleaned_name.replace(":", ""),
            cleaned_name.replace(",", ""),
            cleaned_name.replace("-", ""),
        ]
        results.update(simplified_variants)

        set_mappings = {
            "festival foil etched": "30th Anniversary Misc Promos",
            "launch weekend foil": "Wizards Play Network 2022",
            "bring a friend": "Love Your LGS 2022",
            "magicfest foil": "MagicFest 2019",
            "warhammer 40,000 commander": [
                "universes beyond warhammer 40000",
                "universes beyond warhammer 40k",
                "warhammer 40000 commander",
                "warhammer 40k commander",
                "cmdr - warhammer 40,000: universes beyond",
                "warhammer 40k singles",
                "universe beyond 40,000",
            ],
            "the lord of the rings: tales of middle-earth commander": [
                "commander lord of the rings",
                "universes beyond lord of the rings commander",
                "universes beyond: lord of the rings - commander",
                "lotr commander",
            ],
            "commander 2024": ["cmdr - 2024"],
            "commander 2023": ["cmdr - 2023"],
            "commander 2022": ["cmdr - 2022"],
            "commander 2021": ["cmdr - 2021"],
            "commander 2020": ["cmdr - 2020"],
            "commander 2019": ["cmdr - 2019"],
            "commander 2018": ["cmdr - 2018"],
            "commander 2017": ["cmdr - 2017"],
            "commander 2016": ["cmdr - 2016"],
            "commander 2015": ["cmdr - 2015"],
            "commander 2014": ["cmdr - 2014"],
            "commander 2013": ["cmdr - 2013"],
            "commander 2012": ["cmdr - 2012"],
            "commander 2011": ["cmdr - 2011"],
            "commander anthology volume ii": ["cmdr - anthology vol. ii", "commander anthology 2"],
            "duel decks: zendikar vs. eldrazi": ["zendikar vs eldrazi duel decks"],
            "the brothers' war retro artifacts": [
                "magic's history: retro or schematic artifact",
                "retro or schematic artifact",
                "retro artifacts",
                "brr",
            ],
            "secret lair drop": [
                "secret lair: heads i win, tails you lose",
                "secret lair",
                "sld",
            ],
            "friday night magic 2022": ["fnm promos", "friday night magic", "fnm promo", "fnm cards"],
            "mystery booster": ["the list", "mystery booster the list"],
            "kamigawa: neon dynasty": ["kamigawa neon destiny"],
            "jurassic world collection": ["universes beyond: jurassic world"],
            "doctor who": ["dr. who (who)", "doctor who (who)" "Dr. Who (WHO)"],
            "from the vault: twenty": ["ftv: twenty"],
            "the brothers' war commander": ["commander brother's war"],
            # "promo pack": [
            #     "pre-release promos",
            #     "shooting stars promos",
            #     "unique promos",
            #     "unique & misc promos",
            # ],
        }

        for candidate in list(results):
            for official_name, variants in set_mappings.items():
                if candidate in variants or candidate == official_name.lower():
                    results.add(official_name.lower())
                    results.update(variants)

        return list(filter(None, results))

    @staticmethod
    def clean_set_name_for_matching(name):
        # Remove descriptors like "Alternate Art", "Extended Art", punctuation, multiple spaces
        name = re.sub(r"[^a-zA-Z0-9\s]", " ", name)  # remove special chars
        name = re.sub(r"\b(alternate|extended|art|showcase|borderless)\b", "", name, flags=re.IGNORECASE)
        return re.sub(r"\s+", " ", name).strip().lower()

    @classmethod
    def get_set_code(cls, set_name):
        """Get set code from set name using exact match first, then fuzzy matching"""
        if not set_name:
            logger.warning("Empty set name provided")
            return None

        logger.debug(f"Getting set code for: {set_name}")

        sets_data = cls.get_sets_data()
        if not sets_data:
            logger.error("No sets data available")
            return None

        # Get all possible normalized forms of the set name
        normalized_names = cls._normalize_set_name(set_name)
        logger.debug(f"Normalized forms: {normalized_names}")

        # Try exact matches first
        for norm_name in normalized_names:
            # Direct match against cache keys
            if norm_name in sets_data:
                logger.debug(f"Exact match found for '{set_name}' using '{norm_name}'")
                return sets_data[norm_name]["code"]

            # Match against set names and codes
            for set_info in sets_data.values():
                if norm_name == set_info["name"].lower() or norm_name == set_info["code"].lower():
                    logger.debug(f"Exact match found against name/code for '{set_name}'")
                    return set_info["code"]

        # Partial matching using "in"
        for norm_name in normalized_names:
            cleaned_norm_name = CardService.clean_set_name_for_matching(norm_name)
            for set_info in sets_data.values():
                cleaned_set_name = CardService.clean_set_name_for_matching(set_info["name"])

                if cleaned_norm_name in cleaned_set_name or cleaned_set_name in cleaned_norm_name:
                    logger.debug(f"Clean partial match found: '{set_name}' -> '{set_info['name']}'")
                    return set_info["code"]

                # Add fuzzy fallback with a threshold
                if fuzz.partial_ratio(cleaned_norm_name, cleaned_set_name) > 85:
                    logger.debug(f"Fuzzy match found: '{set_name}' -> '{set_info['name']}'")
                    return set_info["code"]

        # If no exact match, try fuzzy matching with all normalized forms
        try:
            best_score = 0
            best_code = None

            for norm_name in normalized_names:
                matches = process.extractBests(
                    norm_name,
                    [s["name"].lower() for s in sets_data.values()],
                    scorer=fuzz.token_set_ratio,  # Changed to token_set_ratio for better partial matches
                    score_cutoff=70,  # Lower threshold
                    limit=1,
                )

                if matches and matches[0][1] > best_score:
                    best_score = matches[0][1]
                    match_name = matches[0][0]
                    # Find the corresponding set code
                    for set_info in sets_data.values():
                        if set_info["name"].lower() == match_name:
                            best_code = set_info["code"]
                            break

            if best_code:
                logger.debug(f"Fuzzy matched '{set_name}' with score: {best_score}")
                return best_code

        except Exception as e:
            logger.error(f"Error during fuzzy matching: {str(e)}")
            return "unknown"  # Fallback on error

        logger.warning(f"No match found for set: {set_name}.")
        logger.warning(f"Normalized names tried: {normalized_names}.")
        return None

    @classmethod
    def get_closest_set_name(cls, unclean_set_name):
        """Get the official set name from an unclean set name input.

        Args:
            unclean_set_name (str): The potentially messy set name to clean

        Returns:
            str: The official set name if found, or the original name if no match
        """
        if not unclean_set_name:
            logger.warning(f"[SET CODE] Empty set name received")
            return None

        sets_data = cls.get_sets_data()
        if not sets_data:
            return unclean_set_name

        normalized_names = cls._normalize_set_name(unclean_set_name)

        # Attempt direct exact match first
        for name_normalized in normalized_names:
            if name_normalized in sets_data:
                return sets_data[name_normalized]["name"]

            if name_normalized in cls.promo_mappings:
                mapped_name = cls.promo_mappings[name_normalized].lower()
                if mapped_name in sets_data:
                    return sets_data[mapped_name]["name"]

        # Attempt fuzzy match against each normalized candidate
        best_match = None
        best_score = 0

        try:
            set_names_lower = [set_info["name"].lower() for set_info in sets_data.values()]
            filtered_candidates = [candidate for candidate in normalized_names if candidate.strip()]

            for candidate in filtered_candidates:
                match = process.extractOne(
                    candidate,
                    set_names_lower,
                    scorer=fuzz.token_set_ratio,
                    score_cutoff=65,  # Lower cutoff to improve partial matching
                )
                if match and match[1] > best_score:
                    best_match = match
                    best_score = match[1]

            if best_match:
                matched_name = best_match[0]
                for set_info in sets_data.values():
                    if set_info["name"].lower() == matched_name:
                        logger.debug(
                            f"Fuzzy matched '{unclean_set_name}' to '{set_info['name']}' with score {best_score}"
                        )
                        return set_info["name"]

        except Exception as e:
            logger.error(f"[SET NAME] Error during fuzzy matching: {str(e)}")

        # Fallback: try to match against set codes
        input_lower = unclean_set_name.lower()
        for set_info in sets_data.values():
            if set_info["code"].lower() == input_lower or input_lower in set_info["code"].lower():
                logger.debug(
                    f"Matched '{unclean_set_name}' directly to set code '{set_info['code']}' ({set_info['name']})"
                )
                return set_info["name"]

        logger.warning(f"[SET NAME] No match found for '{unclean_set_name}', returning original.")
        return unclean_set_name

    @classmethod
    def get_clean_set_code_from_set_name(cls, unclean_set_name):
        """Get the official set code from an unclean set name input.

        Args:
            unclean_set_name (str): The potentially messy set name to clean

        Returns:
            str: The official set code if found, or 'unknown' if no match
        """
        # First get the proper set name
        clean_set_name = cls.get_closest_set_name(unclean_set_name)
        if not clean_set_name:
            logger.warning(f"[SET CODE] No clean set name found for: {unclean_set_name}")
            return None

        # Then get the set code using the existing method
        return cls.get_set_code(clean_set_name)

    # @classmethod
    # def _find_full_set_name(cls, code):
    #     """Find full set name from a set code."""
    #     # Common set code to full name mappings
    #     known_sets = {
    #         "znr": "zendikar rising",
    #         "afr": "adventures in the forgotten realms",
    #         "neo": "kamigawa neon dynasty",
    #         "dmu": "dominaria united",
    #         "one": "phyrexia all will be one",
    #         "mom": "march of the machine",
    #         "ltr": "lord of the rings",
    #         "bro": "the brothers war",
    #         "woe": "wilds of eldraine",
    #         "lci": "lost caverns of ixalan",
    #         "mkm": "murders at karlov manor",
    #         "who": "doctor who",
    #         "mat": "march of the machine aftermath",
    #         "mid": "innistrad midnight hunt",
    #         "vow": "innistrad crimson vow",
    #         "snc": "streets of new capenna",
    #         "ncc": "new capenna commander",
    #         "clb": "commander legends battle for baldurs gate",
    #         "40k": "warhammer 40000",
    #         "dmc": "dominaria united commander",
    #         "brc": "brother's war commander",
    #         # Add more as needed
    #     }
    #     return known_sets.get(code.lower())

    # @classmethod
    # def _get_all_set_variants(cls, set_name):
    #     """Get all possible variants of a set name including extras versions."""
    #     variants = []
    #     name_lower = set_name.lower()

    #     # Base variants
    #     variants.extend(
    #         [
    #             name_lower,
    #             name_lower.replace(" ", ""),
    #             name_lower.replace(":", ""),
    #             name_lower.replace(":", " "),
    #         ]
    #     )

    #     # Add extras variants
    #     extras_variants = [
    #         f"{name_lower} extras",
    #         f"{name_lower}: extras",
    #         f"{name_lower}:extras",
    #     ]
    #     variants.extend(extras_variants)

    #     # If it's a known set code, add full name variants
    #     full_name = cls._find_full_set_name(name_lower)
    #     if full_name:
    #         full_variants = [
    #             full_name,
    #             f"{full_name} extras",
    #             f"{full_name}: extras",
    #             full_name.replace(" ", ""),
    #             full_name.replace(":", ""),
    #         ]
    #         variants.extend(full_variants)

    #     # Remove duplicates and empty strings
    #     return list(set(v for v in variants if v))

    @staticmethod
    def extract_magic_set_from_href(url):
        try:
            sets_data = CardService.get_sets_data()
            known_sets = sets_data.keys()

            # Normalize URL for robust matching
            normalized_url = url.lower().replace("_", " ").replace("-", " ").replace("/", " ")

            # Check against known sets directly (robust extraction)
            for known_set in known_sets:
                normalized_known_set = known_set.lower()
                if normalized_known_set in normalized_url:
                    return known_set  # Immediately return the matched known set

            # Fallback logic based on "singles-" if no direct matches found
            if "singles-" in url:
                part = url.split("singles-")[-1].split("/")[0]
                potential_set_name = part.replace("-brawl", "").replace("_", " ").replace("-", " ").strip()

                # Validate the extracted potential set name with fuzzy matching
                best_match = process.extractOne(
                    potential_set_name, known_sets, scorer=fuzz.token_set_ratio, score_cutoff=70
                )
                if best_match:
                    return best_match[0]  # Return validated fuzzy matched set

            logger.warning(f"No magic set extracted reliably from URL: {url}")
            return None

        except Exception as e:
            logger.error(f"Fatal error in extract_magic_set: {str(e)}", exc_info=True)
            return None

    @staticmethod
    def get_next_buylist_id(user_id):
        """
        Get the next available buylist_id for a user by finding the maximum and incrementing.

        Args:
            user_id (int): The ID of the user.

        Returns:
            int: The next available buylist_id.
        """
        try:
            with CardService.transaction_context() as session:
                # Query for the maximum buylist_id for the given user_id
                max_buylist_id = session.query(func.max(UserBuylist.id)).filter(UserBuylist.user_id == user_id).scalar()

                # Increment the maximum buylist_id or start from 1 if no buylists exist
                return (max_buylist_id or 0) + 1
        except Exception as e:
            logger.error(f"Error fetching max buylist_id for user {user_id}: {str(e)}")
            raise

    #  Card Operations
    @staticmethod
    def get_all_user_buylist_cards(user_id):
        return UserBuylistCard.query.filter_by(user_id=user_id).all()

    # @staticmethod
    # def get_user_buylist_card_by_id(card_id):
    #     """
    #     Get a specific card from the user's buylist by ID.
    #     """
    #     return UserBuylistCard.query.filter_by(id=card_id).first()

    @staticmethod
    def add_user_buylist_card(
        card_id=None,
        name=None,
        set_name=None,
        language="English",
        quality="NM",
        quantity=1,
        version="Standard",
        foil=False,
        buylist_id=None,
        user_id=None,
    ):
        """Save a new card or update an existing card with proper validation and error handling"""
        try:
            with CardService.transaction_context():
                if not name:
                    raise ValueError("Card name is required")

                if quantity < 1:
                    raise ValueError("Quantity must be positive")

                # Get set code if set_name is provided
                set_code = None
                if set_name:
                    set_code = CardService.get_clean_set_code_from_set_name(set_name)
                    if not set_code:
                        raise ValueError(f"Invalid set name: {set_name}")
                    logger.info(f"Mapped set name '{set_name}' to code '{set_code}'")

                if card_id:
                    card = UserBuylistCard.query.get(card_id)
                    if not card:
                        raise ValueError(f"Card with ID {card_id} not found")

                    card.name = name
                    card.set_code = set_code
                    card.set_name = set_name
                    card.language = language
                    card.quantity = quantity
                    card.version = version
                    card.foil = foil
                    card.buylist_id = buylist_id
                    card.user_id = user_id
                else:
                    card = UserBuylistCard(
                        name=name,
                        set_name=set_name,
                        set_code=set_code,
                        language=language,
                        quality=quality,
                        quantity=quantity,
                        version=version,
                        foil=foil,
                        buylist_id=buylist_id,
                        user_id=user_id,
                    )
                    db.session.add(card)

                return card
        except Exception as e:
            logger.error(f"Error saving card: {str(e)}")
            raise

    @staticmethod
    def update_user_buylist_card(card_id, data):
        """Update a specific card in the user's buylist."""
        try:
            current_app.logger.info(f"Updating card {card_id} with data: {data}")

            card = UserBuylistCard.query.get(card_id)
            if not card:
                return None

            buylist_id = data.get("buylist_id")
            if not buylist_id:
                raise ValueError("Buylist ID is required")

            buylist = UserBuylist.query.get(buylist_id)
            if not buylist:
                raise ValueError("Buylist does not exist")

            if card.buylist_id != buylist_id:
                raise ValueError("Card does not belong to the provided buylist")

            card.name = data.get("name", card.name)
            card.set_code = data.get("set_code", card.set_code)
            card.set_name = data.get("set_name", card.set_name)
            card.language = data.get("language", card.language)
            card.quantity = data.get("quantity", card.quantity)
            card.quality = data.get("quality", card.quality)
            card.version = data.get("version", card.version)
            card.foil = data.get("foil", card.foil)

            db.session.commit()
            return card
        except Exception as e:
            current_app.logger.error(f"Error updating card: {str(e)}")
            db.session.rollback()
            raise

    @staticmethod
    def update_user_buylist_name(id, user_id, newbuylist_name):
        """Update the name of a specific buylist for a user."""
        # Find the buylist
        buylist = UserBuylist.query.filter_by(id=id, user_id=user_id).first()

        if not buylist:
            raise ValueError("Buylist does not exist.")

        buylist.name = newbuylist_name
        db.session.commit()
        current_app.logger.info(f"Buylist '{buylist.name}' updated successfully")
        return buylist

    @staticmethod
    def get_all_buylists(user_id):
        """Retrieve all unique buylists for a specific user."""
        try:
            buylists = db.session.query(UserBuylist.id, UserBuylist.name).filter(UserBuylist.user_id == user_id).all()

            return [{"id": buylist.id, "name": buylist.name or "Unnamed Buylist"} for buylist in buylists]
        except Exception as e:
            logger.error(f"Error fetching buylists: {str(e)}")
            raise

    @staticmethod
    def get_top_buylists(user_id, limit=3):
        """Get the top 'limit' buylists for a specific user, sorted by most recently updated."""
        try:
            buylists = (
                db.session.query(UserBuylist.id, UserBuylist.name)
                .filter(UserBuylist.user_id == user_id)
                .order_by(UserBuylist.updated_at.desc())
                .limit(limit)
                .all()
            )

            return [{"id": buylist.id, "name": buylist.name} for buylist in buylists]
        except Exception as e:
            logger.error(f"Error fetching top buylists: {str(e)}")
            raise

    @staticmethod
    def create_buylist(name, user_id):
        buylist = UserBuylist(name=name, user_id=user_id)
        db.session.add(buylist)
        db.session.commit()
        db.session.refresh(buylist)
        return buylist

    @staticmethod
    def add_card_to_buylist(user_id, id, cards_data):
        """
        Adds cards to a buylist, preventing duplicates.
        """
        buylist = UserBuylist.query.get(id)
        if not buylist:
            raise ValueError("Buylist does not exist.")

        if not cards_data:
            raise ValueError("No cards provided.")

        try:
            with CardService.transaction_context():
                existing_cards = {c.name.lower() for c in buylist.cards}

                for card in cards_data:
                    card_name = card["name"].strip().lower()
                    if card_name in existing_cards:
                        continue  # Skip duplicate cards

                    new_card = UserBuylistCard(
                        user_id=user_id,
                        buylist_id=id,
                        name=card["name"],
                        set_name=card["set_name"],
                        set_code=card["set_code"],
                        language=card["language"],
                        quantity=card["quantity"],
                        version=card["version"],
                        foil=card["foil"],
                    )
                    db.session.add(new_card)

                db.session.commit()
                return buylist
        except Exception as e:
            logger.error(f"Error adding cards to buylist: {str(e)}")
            raise

    @staticmethod
    def delete_buylist(id, user_id):
        """
        Deletes a buylist and all associated cards by its ID and user.

        Args:
            buylist_id (int): The ID of the buylist to delete.
            user_id (int): The ID of the user who owns the buylist.

        Returns:
            bool: True if the buylist was deleted, False otherwise.
        """
        try:
            with CardService.transaction_context():
                # ✅ Check if the buylist exists
                buylist = UserBuylist.query.filter_by(id=id, user_id=user_id).first()
                if not buylist:
                    logger.warning(f"Buylist {id} not found for user {user_id}.")
                    return False

                # ✅ Delete all associated cards
                db.session.query(UserBuylistCard).filter_by(buylist_id=id, user_id=user_id).delete()

                # ✅ Delete the buylist itself
                db.session.delete(buylist)

                # ✅ Commit the transaction once
                db.session.commit()

                logger.info(f"Buylist {id} and all associated cards deleted successfully.")
                return True

        except Exception as e:
            logger.error(f"Error deleting buylist {id}: {str(e)}")
            return False

    @staticmethod
    def delete_card_from_buylist(id, card_name, quantity, user_id):
        """
        Deletes a card from the specified buylist.

        Args:
            buylist_id (int): The ID of the buylist.
            card_name (str): The name of the card to delete.
            quantity (int): The quantity of the card to remove.
            user_id (int): The ID of the user performing the operation.

        Returns:
            bool: True if the card was successfully deleted, False otherwise.
        """
        try:
            with CardService.transaction_context():
                # Query for the card in the user's buylist
                card = UserBuylistCard.query.filter_by(buylist_id=id, name=card_name, user_id=user_id).first()

                if not card:
                    logger.warning(f"Card '{card_name}' not found in buylist ID {id}.")
                    return False

                # If the card exists, adjust quantity or delete it
                if card.quantity > quantity:
                    card.quantity -= quantity
                    logger.info(
                        f"Reduced quantity of '{card_name}' in buylist ID {id} by {quantity}. Remaining: {card.quantity}."
                    )
                else:
                    db.session.delete(card)
                    logger.info(f"Deleted '{card_name}' from buylist ID {id}.")

                return True
        except Exception as e:
            logger.error(f"Error deleting card '{card_name}' from buylist ID {id}: {str(e)}")
            return False

    # @staticmethod
    # def get_buylist_by_id(buylist_id):
    #     """Get a saved buylist by ID."""
    #     try:
    #         return UserBuylistCard.query.get(buylist_id)
    #     except Exception as e:
    #         logger.error(f"Error fetching buylist: {str(e)}")
    #         raise

    # @staticmethod
    # def get_buylist_by_name(buylist_name):
    #     """Get a saved buylist by name."""
    #     try:
    #         return UserBuylist.query.filter_by(name=buylist_name).all()
    #     except Exception as e:
    #         logger.error(f"Error fetching buylist: {str(e)}")
    #         raise

    @staticmethod
    def get_buylist_cards_by_id(id):
        """Get all cards for a specific buylist by ID."""
        try:
            return UserBuylistCard.query.filter_by(buylist_id=id).all()
        except Exception as e:
            logger.error(f"Error fetching buylist cards: {str(e)}")
            raise

    @staticmethod
    def fetch_scryfall_data(card_name, set_code=None, language=None, version=None):
        current_app.logger.info(f"Fetching Scryfall data for: {card_name} (set: {set_code})")

        try:
            # First try exact match with set
            params = {
                "exact": card_name,
                "set": set_code if set_code else None,
                "lang": language if language else "en",
            }
            # Remove None values
            params = {k: v for k, v in params.items() if v is not None}

            current_app.logger.info(f"Making exact request to Scryfall with params: {params}")
            response = requests.get(SCRYFALL_API_NAMED_URL, params=params)

            if response.status_code != 200:
                # If exact match fails, try fuzzy search
                current_app.logger.info("Exact match failed, trying fuzzy search")
                params["fuzzy"] = card_name
                del params["exact"]
                response = requests.get(SCRYFALL_API_NAMED_URL, params=params)

                if response.status_code != 200:
                    current_app.logger.error(f"Scryfall API error: {response.text}")
                    return None

            card_data = response.json()
            current_app.logger.info(f"Successfully retrieved card data for: {card_name} (set: {set_code})")

            # Fetch all printings
            all_printings = []
            if prints_uri := card_data.get("prints_search_uri"):
                prints_response = requests.get(prints_uri)
                if prints_response.status_code == 200:
                    prints_data = prints_response.json()
                    all_printings = [
                        {
                            "id": print_data.get("id"),
                            "name": print_data.get("name"),
                            "set_code": print_data.get("set"),
                            "set_name": print_data.get("set_name"),
                            "collector_number": print_data.get("collector_number"),
                            "rarity": print_data.get("rarity"),
                            "image_uris": print_data.get("image_uris", {}),
                            "prices": print_data.get("prices", {}),
                            "digital": print_data.get("digital", False),
                            "lang": print_data.get("lang", "en"),
                        }
                        for print_data in prints_data.get("data", [])
                    ]

            result = {
                "scryfall": {**card_data, "all_printings": all_printings},
                "scan_timestamp": datetime.now().isoformat(),
            }

            current_app.logger.info(f"Returning data structure with {len(all_printings)} printings")
            return result

        except Exception as e:
            current_app.logger.error(f"Error in fetch_scryfall_data: {str(e)}", exc_info=True)
            return None

    @staticmethod
    def fetch_scryfall_card_data(card_name, set_code=None, language=None, version=None):
        try:
            data = CardService.fetch_scryfall_data(card_name, set_code, language, version)
            if not data:
                current_app.logger.debug(f"No data found for card '{card_name}'")
                return None
            return data
        except Exception as e:
            current_app.logger.error(f"Error in fetch_card_data: {str(e)}")
            return None

    # @staticmethod
    # def fetch_all_printings(prints_search_uri):
    #     all_printings = []
    #     next_page = prints_search_uri

    #     while next_page:
    #         try:
    #             response = requests.get(next_page)
    #             response.raise_for_status()
    #         except requests.exceptions.RequestException as e:
    #             current_app.logger.error(f"Error fetching printings data from Scryfall: {str(e)}")
    #             return []

    #         data = response.json()
    #         current_app.logger.debug(f"Scryfall all printings data for page: {data}")

    #         for card in data.get('data', []):
    #             current_app.logger.debug(f"Processing card printing: {card}")
    #             all_printings.append({
    #                 'set_code': card.get('set'),
    #                 'set_name': card.get('set_name'),
    #                 'rarity': card.get('rarity'),
    #                 'collector_number': card.get('collector_number'),
    #                 'prices': card.get('prices'),
    #                 'scryfall_uri': card.get('scryfall_uri'),
    #                 'image_uris': card.get('image_uris')  # Include image_uris for hover previews
    #             })

    #         next_page = data.get('next_page')

    #     return all_printings

    @staticmethod
    def get_card_suggestions(query, limit=20):
        scryfall_api_url = f"{SCRYFALL_API_BASE}/catalog/card-names"
        try:
            response = requests.get(scryfall_api_url)
            response.raise_for_status()
            all_card_names = response.json()["data"]
            # Filter card names based on the query
            suggestions = [name for name in all_card_names if query.lower() in name.lower()]
            return suggestions[:limit]  # Return only up to the limit
        except requests.RequestException as e:
            logger.error("Error fetching card suggestions from Scryfall: %s", str(e))
            return []

    @staticmethod
    def validate_card_data(card_data):
        """Validate card data before saving"""
        errors = []

        # Required fields validation
        if not card_data.get("name"):
            errors.append("Card name is required")

        # Set validation - either set_name or set_code should be present
        if not card_data.get("set_name") and not card_data.get("set_code"):
            errors.append("Either set name or set code must be provided")

        # Quantity validation
        quantity = card_data.get("quantity", 0)
        if not isinstance(quantity, int) or quantity < 0:
            errors.append("Quantity must be a positive integer")

        # Language validation
        valid_languages = [lang.value for lang in CardLanguage]
        if card_data.get("language") and card_data.get("language") not in valid_languages:
            errors.append(f"Invalid language. Must be one of: {', '.join(valid_languages)}")

        # Version validation
        valid_versions = [version.value for version in CardVersion]
        if card_data.get("version") and card_data.get("version") not in valid_versions:
            errors.append(f"Invalid version. Must be one of: {', '.join(valid_versions)}")

        # Foil validation
        if not isinstance(card_data.get("foil", False), bool):
            errors.append("Foil must be a boolean value")

        return errors

    @staticmethod
    def generate_purchase_links(purchase_data):
        """
        Generate properly formatted purchase URLs for cards grouped by site.

        Args:
            purchase_data (list): List of dicts containing card_name and site_name.

        Returns:
            list: List of dicts with site info and formatted purchase URLs.
        """
        results = []
        try:
            # Fetch all active sites from SiteService
            active_sites = {site.id: site for site in SiteService.get_all_sites()}

            # Process each store's cards
            for store in purchase_data:
                try:
                    site_id = store.get("site_id")
                    cards = store.get("cards", [])

                    if not site_id:
                        logger.warning(f"Missing site_id in store data: {store}")
                        continue

                    # Fetch site details
                    site = active_sites.get(site_id)
                    if not site:
                        logger.warning(f"Site with ID {site_id} not found in active sites.")
                        continue

                    if not cards:
                        logger.warning(f"No cards to process for site with ID {site_id}.")
                        continue

                    # Generate payload and URLs based on site method
                    site_method = site.method.lower() if hasattr(site, "method") else ""

                    if site_method in ["crystal", "scrapper"]:
                        payload = {
                            "authenticity_token": "Dwn7IuTOGRMC6ekxD8lNnJWrsg45BVs85YplhjuFzbM=",
                            "query": "\n".join(card.get("name", "") for card in cards if card.get("name")),
                            "submit": "Continue",
                        }
                        purchase_url = site.url
                    elif site_method == "shopify":
                        card_names = [card.get("name", "") for card in cards if card.get("name")]
                        purchase_url, payload = CardService.create_shopify_url_and_payload(site, card_names)
                    elif site_method == "hawk":
                        purchase_url, payload = CardService.create_hawk_url_and_payload(site, cards)
                    else:
                        logger.warning(f"Unsupported purchase method '{site_method}' for site ID {site_id}.")
                        continue

                    # Add the result
                    results.append(
                        {
                            "site_name": store.get("site_name", f"Unknown Site {site_id}"),
                            "site_id": site_id,
                            "purchase_url": purchase_url,
                            "payload": payload,
                            "method": site_method,
                            "country": getattr(site, "country", "Unknown"),
                            "cards": cards,
                            "card_count": len(cards),
                        }
                    )

                    logger.info(f"Generated purchase link for site {store.get('site_name')} with {len(cards)} cards.")

                except Exception as e:
                    logger.error(f"Error processing store {store.get('site_name', 'Unknown')}: {str(e)}")
                    continue

        except Exception as e:
            logger.error(f"Error in generate_purchase_links: {str(e)}")
            logger.exception("Full traceback:")

        return results

    @staticmethod
    def create_shopify_url_and_payload(site, card_names):
        try:
            # Format the payload
            payload = [{"card": name, "quantity": 1} for name in card_names]
            # URLs
            api_url = ""
            base_url = "https://api.binderpos.com/external/shopify/decklist"
            alternate_url = "https://portal.binderpos.com/external/shopify/decklist"

            # Determine the correct API URL based on site name
            if hasattr(site, "api_url") and site.api_url:
                if "kingdomtitans" in site.url:
                    api_url = alternate_url + f"?storeUrl={site.api_url}&type=mtg"
                else:
                    api_url = base_url + f"?storeUrl={site.api_url}&type=mtg"

            # Make the request
            json_payload = json.dumps(payload)  # Convert list to JSON string
            return api_url, json_payload
        except Exception as e:
            logger.error(f"Error creating Shopify request for {site.name}: {str(e)}")
            return None

    def create_hawk_url_and_payload(site, card_name):
        try:
            api_url = "https://essearchapi-na.hawksearch.com/api/v2/search"
            # Format query based on card name type
            if "//" in card_name:
                # Handle double-faced cards
                front, back = map(str.strip, card_name.split("//"))
                query = f'card\\ name.text: "{front}" AND card\\ name\\ 2.text: "{back}"'
            else:
                # Handle regular cards including those with quotes or special characters
                # Keep any existing quotes in the name
                escaped_name = card_name.replace('"', '\\"')  # Escape any existing quotes
                if '"' in card_name:
                    # Card already has quotes, use as is
                    query = f'card\\ name.text: "{escaped_name}"'
                else:
                    # Regular card name
                    query = f'card\\ name.text: "{escaped_name}"'

            payload = {
                "ClientData": {"VisitorId": str(uuid.uuid4())},
                "ClientGuid": "30c874915d164f71bf6f84f594bf623f",
                "FacetSelections": {"tab": ["Magic"], "child_inventory_level": ["1"]},
                "query": query,
                "SortBy": "score",
            }

            json_payload = json.dumps(payload)
            return api_url, json_payload
        except Exception as e:
            logger.error(f"Error creating hawk request for {site.name}: {str(e)}")
            return None
