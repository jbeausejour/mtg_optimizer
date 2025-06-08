import json
import re
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

import aiohttp
import asyncio

# Use aioredis instead of synchronous redis client
import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from app import redis_host
from app.services.async_base_service import AsyncBaseService

from thefuzz import fuzz, process
import contextvars
from redis.asyncio import Redis

_redis_ctx = contextvars.ContextVar("redis_client")

logger = logging.getLogger(__name__)

SCRYFALL_API_BASE = "https://api.scryfall.com"
SCRYFALL_SETS_URL = f"{SCRYFALL_API_BASE}/sets"

SCRYFALL_API_NAMED_URL = f"{SCRYFALL_API_BASE}/cards/named"
CARDCONDUIT_URL = "https://cardconduit.com/buylist"

REDIS_PORT = 6379
CACHE_EXPIRATION = 86400  # 24 hours (same as card names)
REDIS_SETS_KEY = "scryfall_set_codes"
REDIS_CARDNAME_KEY = "scryfall_card_names"
SCRYFALL_CACHE = {}
SCRYFALL_CACHE_LOCK = asyncio.Lock()


class CardService(AsyncBaseService):

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
        "#045 - duel decks m14/63/64/67": "Duel Decks: Zendikar vs. Eldrazi",
        "duel decks m14/m63/m64": "Duel Decks: Zendikar vs. Eldrazi",
        "cbl bundle promo": "Commander Legends: Battle for Baldur's Gate",
        "treasure chest promo": "Treasure Chest",
        "promos: miscellaneous": "Judge Gift Cards",
        "brawl deck exclusive": "Commander Collection",
        "brawl": "Commander Collection",
        "the list": "Mystery Booster: The List",
        "set boosters reserved list": "Mystery Booster: The List",
    }

    ##################
    # Redis Operations
    ##################
    @staticmethod
    async def get_redis_client() -> Redis:
        try:
            return _redis_ctx.get()
        except LookupError:
            client = await aioredis.from_url(
                f"redis://{redis_host}:{REDIS_PORT}", db=0, encoding="utf-8", decode_responses=True
            )
            _redis_ctx.set(client)
            return client

    @staticmethod
    async def close_redis_client():
        """Close the Redis client connection."""
        if hasattr(CardService, "_redis_client"):
            CardService._redis_client.close()
            await CardService._redis_client.wait_closed()
            delattr(CardService, "_redis_client")

    ##################
    # Cache Operations
    ##################
    @classmethod
    async def initialize_card_names_cache(cls):
        """Initialize cache during application startup."""
        logger.info("Initializing card names cache...")
        success = await cls.ensure_card_names_cache()
        if success:
            logger.info("Card names cache initialized successfully")
        else:
            logger.error("Failed to initialize card names cache")
        return success

    @classmethod
    async def ensure_sets_cache(cls) -> bool:
        """
        Ensure sets cache exists. Only fetches if missing.
        Returns True if cache is available, False if failed to create.
        """
        redis_client = await cls.get_redis_client()

        # Check if cache exists
        if await redis_client.exists(REDIS_SETS_KEY):
            return True

        # Cache doesn't exist - fetch it once
        logger.info("Sets cache missing, initializing...")
        sets_data = await cls.fetch_scryfall_set_codes()
        return len(sets_data) > 0

    @classmethod
    async def initialize_sets_cache(cls):
        """Initialize sets cache during application startup."""
        logger.info("Initializing sets cache...")
        success = await cls.ensure_sets_cache()
        if success:
            logger.info("Sets cache initialized successfully")
        else:
            logger.error("Failed to initialize sets cache")
        return success

    @classmethod
    async def ensure_card_names_cache(cls) -> bool:
        """
        Ensure card names cache exists. Only fetches if missing.
        Returns True if cache is available, False if failed to create.
        """
        redis_client = await cls.get_redis_client()

        # Check if cache exists
        if await redis_client.exists(REDIS_CARDNAME_KEY):
            return True

        # Cache doesn't exist - fetch it once
        logger.info("Card names cache missing, initializing...")
        names = await cls.fetch_scryfall_card_names()
        return len(names) > 0

    @classmethod
    async def get_cached_card_names(cls) -> List[str]:
        """
        Get cached card names. Does NOT fetch if missing - returns empty list.
        Use ensure_card_names_cache() first if you need to guarantee cache exists.
        """
        redis_client = await cls.get_redis_client()

        cached_names_json = await redis_client.get(REDIS_CARDNAME_KEY)
        if not cached_names_json:
            logger.warning("Card names cache is empty")
            return []

        try:
            return json.loads(cached_names_json)
        except json.JSONDecodeError:
            logger.error("Failed to parse cached card names")
            return []

    @classmethod
    async def get_cached_sets(cls) -> Dict[str, Dict[str, Any]]:
        """
        Get cached sets data. Does NOT fetch if missing - returns empty dict.
        Use ensure_sets_cache() first if you need to guarantee cache exists.
        """
        redis_client = await cls.get_redis_client()

        cached_sets_json = await redis_client.get(REDIS_SETS_KEY)
        if not cached_sets_json:
            logger.warning("Sets cache is empty")
            return {}

        try:
            return json.loads(cached_sets_json)
        except json.JSONDecodeError:
            logger.error("Failed to parse cached sets")
            return {}

    ##################
    # Fetch Operations
    ##################
    @classmethod
    async def fetch_scryfall_card_names_async(cls, session: AsyncSession):
        """Async version of fetch_scryfall_card_names that accepts a session"""
        # This method doesn't actually use the session, but we include it for consistency
        return await cls.fetch_scryfall_card_names()

    @staticmethod
    async def fetch_scryfall_card_names():
        """Fetch the full list of valid card names from Scryfall and cache OFFICIAL names in Redis."""
        redis_client = await CardService.get_redis_client()

        try:
            logger.info("Fetching full card list from Scryfall...")
            async with aiohttp.ClientSession() as session:
                async with session.get("https://api.scryfall.com/catalog/card-names") as response:
                    response.raise_for_status()
                    data = await response.json()
                    official_card_names = data.get("data", [])

            # Store the OFFICIAL names directly (no lowercasing!)
            all_card_names = set()

            for official_name in official_card_names:
                # Add the official name
                all_card_names.add(official_name)

                # Handle double-sided cards - add each side as well
                if " // " in official_name:
                    parts = official_name.split(" // ")
                    for part in parts:
                        part_stripped = part.strip()
                        if part_stripped:
                            all_card_names.add(part_stripped)

            # Store ONLY the official names in Redis
            await redis_client.set(REDIS_CARDNAME_KEY, json.dumps(list(all_card_names)))

            logger.info(f"Cached {len(all_card_names)} official card names.")
            return all_card_names

        except Exception as e:
            logger.error(f"Error fetching Scryfall card names: {str(e)}")
            return set()

    @classmethod
    async def fetch_scryfall_set_codes_async(cls, session: AsyncSession):
        """Async version of fetch_scryfall_set_codes that accepts a session"""
        # This method doesn't actually use the session, but we include it for consistency
        return await cls.fetch_scryfall_set_codes()

    @staticmethod
    async def fetch_scryfall_set_codes():
        """Fetch all set codes from Scryfall API and cache them in Redis."""
        redis_client = await CardService.get_redis_client()

        try:
            logger.info("Fetching all set codes from Scryfall...")
            async with aiohttp.ClientSession() as session:
                async with session.get(SCRYFALL_SETS_URL) as response:
                    response.raise_for_status()
                    data = await response.json()
                    sets_data = data.get("data", [])

            # Process sets into a dictionary
            sets_dict = {}
            for set_data in sets_data:
                set_name = set_data.get("name")
                if set_name:
                    sets_dict[set_name.lower()] = {
                        "code": set_data.get("code"),
                        "released_at": set_data.get("released_at"),
                        "set_type": set_data.get("set_type"),
                    }

            # Cache in Redis
            await redis_client.set(REDIS_SETS_KEY, json.dumps(sets_dict), ex=CACHE_EXPIRATION)
            logger.info(f"Cached {len(sets_dict)} Scryfall sets.")
            return sets_dict

        except Exception as e:
            logger.error(f"Error fetching Scryfall sets: {str(e)}")
            return {}

    @classmethod
    async def fetch_all_sets(cls) -> List[Dict[str, str]]:
        """Fetch all valid sets from Redis (cached from Scryfall)."""
        # Ensure cache exists
        if not await cls.ensure_sets_cache():
            logger.error("Could not initialize sets cache")
            return []

        # Get cached data
        sets_data = await cls.get_cached_sets()
        if not sets_data:
            return []

        return [{"set": data["code"], "name": name} for name, data in sets_data.items()]

    @classmethod
    async def fetch_scryfall_card_data(
        cls,
        session: AsyncSession,
        card_name: str,
        set_code: Optional[str] = None,
        language: Optional[str] = None,
        version: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        def extract_available_versions(printing: dict) -> dict:
            return {
                "finishes": printing.get("finishes", []),
                "frame_effects": printing.get("frame_effects", []),
                "full_art": printing.get("full_art", False),
                "textless": printing.get("textless", False),
                "border_color": printing.get("border_color", ""),
            }

        cache_key = f"{card_name.lower()}|{set_code or ''}|{language or 'en'}|{version or ''}"

        async with SCRYFALL_CACHE_LOCK:
            if cache_key in SCRYFALL_CACHE:
                logger.debug(f"[CACHE HIT] Scryfall for: {cache_key}")
                return SCRYFALL_CACHE[cache_key]

        logger.debug(f"[CACHE MISS] Scryfall for: {cache_key}")

        # ISSUE 1: Missing required headers
        headers = {
            "User-Agent": "MTGCardService/1.0",  # Required by Scryfall API
            "Accept": "application/json",  # Required by Scryfall API
        }

        try:
            # ISSUE 2: Strip and normalize card name to handle edge cases
            normalized_card_name = card_name.strip()

            params = {
                "exact": normalized_card_name,
                "set": set_code,
                "lang": language or "en",
            }
            params = {k: v for k, v in params.items() if v is not None}

            async with aiohttp.ClientSession(headers=headers) as http_session:
                # ISSUE 3: Add timeout and better error handling
                timeout = aiohttp.ClientTimeout(total=30)

                # Fetch main card data with exact match
                logger.info(f"Making exact request for: {normalized_card_name} with params: {params}")
                async with http_session.get(SCRYFALL_API_NAMED_URL, params=params, timeout=timeout) as response:
                    logger.info(f"Exact search response status: {response.status} for card: {normalized_card_name}")

                    if response.status == 200:
                        card_data = await response.json()
                        logger.info(f"Successfully fetched exact match for: {normalized_card_name}")
                    elif response.status == 404:
                        # Try fuzzy search as fallback
                        logger.info(f"Exact match failed (404), trying fuzzy search for: {normalized_card_name}")
                        fuzzy_params = {k: v for k, v in params.items() if k != "exact"}
                        fuzzy_params["fuzzy"] = normalized_card_name

                        async with http_session.get(
                            SCRYFALL_API_NAMED_URL, params=fuzzy_params, timeout=timeout
                        ) as fuzzy_response:
                            logger.info(
                                f"Fuzzy search response status: {fuzzy_response.status} for card: {normalized_card_name}"
                            )

                            if fuzzy_response.status == 200:
                                card_data = await fuzzy_response.json()
                                logger.info(f"Successfully fetched fuzzy match for: {normalized_card_name}")
                            else:
                                # ISSUE 4: Better error logging
                                error_text = await fuzzy_response.text()
                                logger.error(
                                    f"Fuzzy search failed for '{normalized_card_name}'. Status: {fuzzy_response.status}, Response: {error_text}"
                                )
                                return None
                    else:
                        # ISSUE 4: Better error logging for non-404 errors
                        error_text = await response.text()
                        logger.error(
                            f"Exact search failed for '{normalized_card_name}'. Status: {response.status}, Response: {error_text}"
                        )
                        return None

                oracle_id = card_data.get("oracle_id")
                if not oracle_id:
                    logger.warning(f"No oracle_id found for card '{normalized_card_name}'")
                    return None

                # Fetch all printings including multilingual
                print_url = (
                    f"https://api.scryfall.com/cards/search?q=oracleid:{oracle_id}&unique=prints&include_multilingual=1"
                )

                logger.info(f"Fetching all printings for oracle_id: {oracle_id}")
                async with http_session.get(print_url, timeout=timeout) as prints_response:
                    if prints_response.status != 200:
                        error_text = await prints_response.text()
                        logger.error(
                            f"Failed to fetch printings for oracle_id {oracle_id}. Status: {prints_response.status}, Response: {error_text}"
                        )
                        return None
                    prints_data = await prints_response.json()
                    all_printings = prints_data.get("data", [])

            # Group printings by a unique key (e.g., set code and collector number)
            from collections import defaultdict

            printing_groups = defaultdict(list)
            for printing in all_printings:
                key = (printing.get("set"), printing.get("collector_number"))
                printing_groups[key].append(printing)

            # Construct list of English printings with available languages
            official_printings = []
            for group in printing_groups.values():
                languages = sorted({p["lang"] for p in group if "lang" in p})
                # Find the English printing
                english_printing = next((p for p in group if p.get("lang") == "en"), None)
                if english_printing:

                    official_printings.append(
                        {
                            "id": english_printing.get("id"),
                            "name": english_printing.get("name"),
                            "set_code": english_printing.get("set"),
                            "set_name": english_printing.get("set_name"),
                            "collector_number": english_printing.get("collector_number"),
                            "artist": english_printing.get("artist"),
                            "rarity": english_printing.get("rarity"),
                            "image_uris": english_printing.get("image_uris", {}),
                            "prices": english_printing.get("prices", {}),
                            "digital": english_printing.get("digital", False),
                            "lang": english_printing.get("lang", "en"),
                            "available_languages": languages,
                            "available_versions": extract_available_versions(english_printing),
                        }
                    )

            enriched_response = {
                "scryfall": {**card_data, "all_printings": official_printings},
                "scan_timestamp": datetime.now().isoformat(),
            }

            async with SCRYFALL_CACHE_LOCK:
                SCRYFALL_CACHE[cache_key] = enriched_response

            return enriched_response

        except Exception as e:
            logger.error(f"Error in fetch_scryfall_card_data: {str(e)}", exc_info=True)
            return None

    ##################
    # Card Operations
    ##################
    @classmethod
    async def get_official_card_name(cls, input_name: str) -> Optional[str]:
        """
        Get the official card name from any input variation.
        Now simplified - just searches the official names with fuzzy matching.
        """
        if not input_name or not input_name.strip():
            return None

        redis_client = await cls.get_redis_client()

        # Get the official names from cache
        cached_names_json = await redis_client.get(REDIS_CARDNAME_KEY)
        if not cached_names_json:
            # Cache miss - rebuild cache
            logger.info("Card names cache miss, rebuilding...")
            await cls.fetch_scryfall_card_names()
            cached_names_json = await redis_client.get(REDIS_CARDNAME_KEY)

        if not cached_names_json:
            logger.error("Could not load card names from cache")
            return None

        try:
            official_names = json.loads(cached_names_json)
        except json.JSONDecodeError:
            logger.error("Failed to parse card names, rebuilding...")
            await cls.fetch_scryfall_card_names()
            return await cls.get_official_card_name(input_name)  # Retry once

        # Normalize the input for searching
        input_lower = input_name.strip().lower()

        # Direct case-insensitive match first
        for official_name in official_names:
            if official_name.lower() == input_lower:
                return official_name

        # Fuzzy matching fallback
        from thefuzz import process, fuzz

        best_match = process.extractOne(
            input_lower, [name.lower() for name in official_names], scorer=fuzz.ratio, score_cutoff=85
        )

        if best_match:
            # Find the original official name that corresponds to the matched lowercase version
            matched_lower = best_match[0]
            for official_name in official_names:
                if official_name.lower() == matched_lower:
                    logger.debug(f"Fuzzy matched '{input_name}' to '{official_name}' with score {best_match[1]}")
                    return official_name

        # Partial matching for double-sided cards
        for official_name in official_names:
            if input_lower in official_name.lower() or official_name.lower() in input_lower:
                if len(input_lower) >= 3 and len(official_name) >= 3:
                    similarity = fuzz.partial_ratio(input_lower, official_name.lower())
                    if similarity >= 80:
                        logger.debug(f"Partial matched '{input_name}' to '{official_name}'")
                        return official_name

        logger.debug(f"No official name found for '{input_name}'")
        return None

    @classmethod
    async def get_card_suggestions(cls, query: str) -> List[str]:
        """Get card suggestions. Requires cache to be initialized."""
        if not query or len(query) < 2:
            return []

        # Ensure cache exists
        if not await cls.ensure_card_names_cache():
            logger.error("Could not initialize card names cache for suggestions")
            return []

        # Get cached names
        official_names = await cls.get_cached_card_names()
        if not official_names:
            return []

        query_lower = query.lower().strip()

        # Find matches
        matches = []
        for official_name in official_names:
            if query_lower in official_name.lower():
                matches.append(official_name)

        # Sort by relevance
        def sort_key(name):
            name_lower = name.lower()
            starts_with_query = 0 if name_lower.startswith(query_lower) else 1
            return (starts_with_query, len(name))

        matches.sort(key=sort_key)
        return matches[:20]

    @classmethod
    async def generate_purchase_links(
        cls, purchase_data: List[Dict[str, Any]], active_sites: Dict[int, Any]
    ) -> List[Dict[str, Any]]:
        """Generate properly formatted purchase URLs for cards grouped by site."""
        results = []
        try:
            for store in purchase_data:
                try:
                    site_id = store.get("site_id")
                    cards = store.get("cards", [])

                    if not site_id:
                        logger.warning(f"Missing site_id in store data: {store}")
                        continue

                    site = active_sites.get(site_id)
                    if not site:
                        logger.warning(f"Site with ID {site_id} not found in active sites.")
                        continue

                    if not cards:
                        logger.warning(f"No cards to process for site with ID {site_id}.")
                        continue

                    card_names = [card.get("name", "") for card in cards if card.get("name")]
                    site_method = site.method.lower() if hasattr(site, "method") else ""
                    purchase_url, payload = None, {}

                    if site_method in ["crystal", "scrapper"]:
                        payload = {
                            "authenticity_token": "Dwn7IuTOGRMC6ekxD8lNnJWrsg45BVs85YplhjuFzbM=",
                            "query": "\n".join(card_names),
                            "submit": "Continue",
                        }
                        purchase_url = site.url

                    elif site_method == "shopify":
                        _, payload = cls.create_shopify_url_and_payload(site, card_names)
                        purchase_url = site.url

                    elif site_method == "f2f":
                        payload = {
                            "pageSize": 0,
                            "filters": [
                                {"field": "Card Name", "values": card_names},
                                {"field": "in_stock", "values": ["1"]},
                            ],
                        }
                        purchase_url = site.url

                    else:
                        logger.warning(f"Unsupported purchase method '{site_method}' for site ID {site_id}.")
                        continue

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
            logger.error(f"Error in generate_purchase_links: {str(e)}", exc_info=True)

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

            # Safely extract site data as dict
            if isinstance(site, dict):
                site_api_url = site.get("api_url", "")
                site_url = site.get("url", "")
                site_name = site.get("name", "Unknown Site")
            else:
                site_api_url = getattr(site, "api_url", "")
                site_url = getattr(site, "url", "")
                site_name = getattr(site, "name", "Unknown Site")

            # Determine the correct API URL based on site name
            if site_api_url:
                if "kingdomtitans" in site_url:
                    api_url = f"{alternate_url}?storeUrl={site_api_url}&type=mtg"
                else:
                    api_url = f"{base_url}?storeUrl={site_api_url}&type=mtg"
            else:
                api_url = ""

            json_payload = json.dumps(payload)
            return api_url, json_payload

        except Exception as e:
            logger.error(f"Error creating Shopify request for {site_name}: {str(e)}")
            return None, None

    @classmethod
    async def is_valid_card_name(cls, card_name: str) -> bool:
        """Check if card name is valid. Requires cache to be initialized."""
        if not card_name or not card_name.strip():
            return False

        # Ensure cache exists
        if not await cls.ensure_card_names_cache():
            logger.error("Could not initialize card names cache for validation")
            return False

        # Get cached names
        official_names = await cls.get_cached_card_names()
        if not official_names:
            return False

        input_lower = card_name.strip().lower()

        # Check against all official names
        for official_name in official_names:
            if official_name.lower() == input_lower:
                return True

            # Handle double-sided cards
            if " // " in official_name:
                sides = official_name.split(" // ")
                for side in sides:
                    if side.strip().lower() == input_lower:
                        return True

        return False

    @staticmethod
    async def extract_magic_set_from_href(url):
        try:

            # Ensure cache exists before getting data
            if not await CardService.ensure_sets_cache():
                logger.error("Could not initialize sets cache")
                return None

            sets_data = await CardService.get_cached_sets()
            if not sets_data:
                return None

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

    @classmethod
    async def get_card_suggestions(cls, query: str) -> List[str]:
        """Get card suggestions. Requires cache to be initialized."""
        if not query or len(query) < 2:
            return []

        # Ensure cache exists
        if not await cls.ensure_card_names_cache():
            logger.error("Could not initialize card names cache for suggestions")
            return []

        # Get cached names
        official_names = await cls.get_cached_card_names()
        if not official_names:
            return []

        query_lower = query.lower().strip()

        # Find matches
        matches = []
        for official_name in official_names:
            if query_lower in official_name.lower():
                matches.append(official_name)

        # Sort by relevance
        def sort_key(name):
            name_lower = name.lower()
            starts_with_query = 0 if name_lower.startswith(query_lower) else 1
            return (starts_with_query, len(name))

        matches.sort(key=sort_key)
        return matches[:20]

    ##################
    # Set Operations
    ##################
    @classmethod
    async def _normalize_set_name(cls, name: str) -> List[str]:
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
        }

        for candidate in list(results):
            for official_name, variants in set_mappings.items():
                if candidate in variants or candidate == official_name.lower():
                    results.add(official_name.lower())
                    results.update(variants)

        return list(filter(None, results))

    @staticmethod
    async def clean_set_name_for_matching(name: str) -> str:
        # Remove descriptors like "Alternate Art", "Extended Art", punctuation, multiple spaces
        name = re.sub(r"[^a-zA-Z0-9\s]", " ", name)  # remove special chars
        name = re.sub(r"\b(alternate|extended|art|showcase|borderless)\b", "", name, flags=re.IGNORECASE)
        return re.sub(r"\s+", " ", name).strip().lower()

    @classmethod
    async def get_sets_data(cls, force_refresh=False):
        """Fetch set data from Redis or refresh if needed."""
        if force_refresh:
            return await cls.fetch_scryfall_set_codes()

        # Ensure cache exists
        if not await cls.ensure_sets_cache():
            logger.error("Could not initialize sets cache")
            return {}

        # Get cached data
        return await cls.get_cached_sets()

    @classmethod
    async def get_set_code(cls, set_name: str) -> Optional[str]:
        """Get set code from set name using exact match first, then fuzzy matching"""
        if not set_name:
            logger.warning("Empty set name provided")
            return None

        logger.debug(f"Getting set code for: {set_name}")

        sets_data = await cls.get_sets_data()
        if not sets_data:
            logger.error("No sets data available")
            return None

        # Get all possible normalized forms of the set name
        normalized_names = await cls._normalize_set_name(set_name)
        logger.debug(f"Normalized forms: {normalized_names}")

        # Try exact matches using keys and code fields
        for norm_name in normalized_names:
            # Direct match against cache keys (outer keys are set names)
            if norm_name in sets_data:
                logger.debug(f"Exact match found for '{set_name}' using outer key '{norm_name}'")
                return sets_data[norm_name].get("code")

            # Match against values' "code" fields
            for outer_name, set_info in sets_data.items():
                if not isinstance(set_info, dict):
                    continue  # Malformed cache entry
                if norm_name == set_info.get("code", "").lower():
                    logger.debug(f"Exact match found against code for '{set_name}' -> {set_info.get('code')}")
                    return set_info.get("code")

        # Try partial matching using cleaned names
        for norm_name in normalized_names:
            cleaned_norm_name = await CardService.clean_set_name_for_matching(norm_name)
            for outer_name, set_info in sets_data.items():
                cleaned_outer = await CardService.clean_set_name_for_matching(outer_name)

                if cleaned_norm_name in cleaned_outer or cleaned_outer in cleaned_norm_name:
                    logger.debug(f"Partial match: '{set_name}' -> '{outer_name}'")
                    return set_info.get("code")

                if fuzz.partial_ratio(cleaned_norm_name, cleaned_outer) > 85:
                    logger.debug(f"Fuzzy partial match: '{set_name}' -> '{outer_name}'")
                    return set_info.get("code")

        # Final fuzzy fallback
        try:
            best_score = 0
            best_code = None

            for norm_name in normalized_names:
                matches = process.extractBests(
                    norm_name,
                    list(sets_data.keys()),
                    scorer=fuzz.token_set_ratio,
                    score_cutoff=70,
                    limit=1,
                )

                if matches:
                    match_name, score = matches[0]
                    if score > best_score:
                        best_score = score
                        best_code = sets_data[match_name].get("code")

            if best_code:
                logger.debug(f"Fuzzy matched '{set_name}' with score {best_score}")
                return best_code

        except Exception as e:
            logger.error(f"Error during fuzzy matching: {str(e)}")
            return None

        logger.debug(f"No match found for set: {set_name}")
        logger.debug(f"Normalized names tried: {normalized_names}")
        return None

    @classmethod
    async def get_closest_set_name(cls, unclean_set_name: str) -> Optional[str]:
        """Get the official set name from an unclean set name input."""
        if not unclean_set_name:
            logger.warning(f"[SET CODE] Empty set name received")
            return None

        sets_data = await cls.get_sets_data()
        if not sets_data:
            return unclean_set_name

        normalized_names = await cls._normalize_set_name(unclean_set_name)

        # Attempt direct exact match first
        for name_normalized in normalized_names:
            if name_normalized in sets_data:
                logger.debug(f"Exact match found for set name: {name_normalized}")
                return name_normalized

            # Check in promo mappings
            if name_normalized in cls.promo_mappings:
                mapped_name = cls.promo_mappings[name_normalized].lower()
                if mapped_name in sets_data:
                    logger.debug(f"Promo mapping matched: {name_normalized} -> {mapped_name}")
                    return mapped_name

        # Fuzzy match using keys only (since 'name' is not in set_info)
        best_match = None
        best_score = 0

        try:
            set_names_lower = list(sets_data.keys())
            filtered_candidates = [candidate for candidate in normalized_names if candidate.strip()]

            for candidate in filtered_candidates:
                match = process.extractOne(candidate, set_names_lower, scorer=fuzz.token_set_ratio, score_cutoff=65)
                if match and match[1] > best_score:
                    best_match = match
                    best_score = match[1]

            if best_match:
                matched_name = best_match[0]
                logger.debug(f"Fuzzy matched '{unclean_set_name}' to '{matched_name}' with score {best_score}")
                return matched_name

        except Exception as e:
            logger.error(f"[SET NAME] Error during fuzzy matching: {str(e)}")

        # Fallback: try to match against set codes
        input_lower = unclean_set_name.lower()
        for outer_name, set_info in sets_data.items():
            if set_info.get("code", "").lower() == input_lower or input_lower in set_info.get("code", "").lower():
                logger.debug(f"Matched '{unclean_set_name}' directly to set code '{set_info['code']}'")
                return outer_name  # The outer_name *is* the set name

        logger.debug(f"[SET NAME] No match found for '{unclean_set_name}', returning original.")
        return unclean_set_name

    @classmethod
    async def get_clean_set_code_from_set_name(cls, unclean_set_name: str) -> Optional[str]:
        """Get the official set code from an unclean set name input."""
        # First get the proper set name
        clean_set_name = await cls.get_closest_set_name(unclean_set_name)
        if not clean_set_name:
            logger.warning(f"[SET CODE] No clean set name found for: {unclean_set_name}")
            return None

        # Then get the set code using the existing method
        return await cls.get_set_code(clean_set_name)
