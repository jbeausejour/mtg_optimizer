from datetime import datetime
import json
import re
import uuid
from sqlalchemy.exc import SQLAlchemyError
import urllib
from app.extensions import db
from app.models.card import UserBuylistCard
from mtgsdk import Card, Set
import logging
import requests
from fuzzywuzzy import fuzz, process
from flask import current_app
from contextlib import contextmanager
from app.constants.card_mappings import CardLanguage, CardVersion
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from app.services.site_service import SiteService

logger = logging.getLogger(__name__)

SCRYFALL_API_BASE = "https://api.scryfall.com"
SCRYFALL_API_NAMED_URL = f"{SCRYFALL_API_BASE}/cards/named"
SCRYFALL_API_SEARCH_URL = f"{SCRYFALL_API_BASE}/cards/search"
SCRYFALL_API_SET_URL = f"{SCRYFALL_API_BASE}/sets"
CARDCONDUIT_URL = "https://cardconduit.com/buylist"

class CardService:
    _sets_cache = {}
    _sets_cache_timestamp = None
    
    @classmethod
    def __init__(cls):
        """Initialize the sets cache during class creation"""
        cls._refresh_sets_cache()
    
    @contextmanager
    def transaction_context():
        """Context manager for database transactions"""
        try:
            yield
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Database error: {str(e)}")
            raise
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error in transaction: {str(e)}")
            raise
        finally:
            db.session.close()

    # Cache realted functions
    @classmethod
    def _refresh_sets_cache(cls):
        """Internal method to refresh the sets cache"""
        try:
            session = cls._get_http_session()
            response = session.get(SCRYFALL_API_SET_URL)
            response.raise_for_status()
            
            data = response.json()
            if not isinstance(data, dict) or 'data' not in data:
                raise ValueError("Invalid response format from Scryfall API")

            sets_data = {}
            excluded_set_types = {"minigame", "alchemy", "box", "memorabilia", "treasure_chest"}
            for set_data in data["data"]:
                try:
                    if set_data["set_type"] in excluded_set_types:
                        continue
                    set_name = set_data["name"].lower()
                    sets_data[set_name] = {
                        "code": set_data["code"],
                        "name": set_data["name"],
                        "released_at": set_data["released_at"],
                        "set_type": set_data["set_type"]
                    }
                except KeyError as e:
                    logger.warning(f"Missing key in set data: {e}")
                    continue

            cls._sets_cache = sets_data
            cls._sets_cache_timestamp = datetime.now()
            logger.info(f"Successfully cached {len(sets_data)} sets")
            
        except Exception as e:
            logger.error(f"Error refreshing sets cache: {str(e)}")
        finally:
            session.close()

    @classmethod
    def _get_http_session(cls):
        """Create session with retry logic"""
        session = requests.Session()
        retries = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504]
        )
        session.mount('https://', HTTPAdapter(max_retries=retries))
        return session

    # Set Operations
    @classmethod
    def get_sets_data(cls, force_refresh=False):
        """Get sets data from cache or refresh if needed"""
        if force_refresh or not cls._sets_cache:
            cls._refresh_sets_cache()
        return cls._sets_cache
    
    @staticmethod
    def fetch_all_sets():
        try:
            sets = Set.all()
            sets_data = [
                {
                    "set": card_set.code,
                    "name": card_set.name,
                    "released_at": card_set.release_date,
                }
                for card_set in sets
            ]
            return sets_data
        except Exception as e:
            current_app.logger.error(f"Error fetching sets data: {str(e)}")
            return []

    @classmethod
    def _normalize_set_name(cls, name):
        """Normalize set name with common variations"""
        if not name:
            return []

        name_lower = name.lower().strip()
        
        # Special handling for "Extras" suffix
        extras_pattern = re.compile(r'^([^:]+)(?::|-)?\s*extras$')
        extras_match = extras_pattern.match(name_lower)
        if extras_match:
            base_set = extras_match.group(1).strip()
            # Get base set name if it exists
            full_set_name = cls._find_full_set_name(base_set)
            extras_variants = [
                name_lower,                    # Original form
                base_set,                      # Base set code
                f"{base_set} extras",          # Space format
                f"{base_set}: extras",         # Colon format
                f"{base_set}:extras",          # No space format
            ]
            if full_set_name:
                extras_variants.extend([
                    full_set_name,                     # Full name
                    f"{full_set_name} extras",         # Full name with extras
                    f"{full_set_name}: extras"         # Full name with colon extras
                ])
            return list(set(var for var in extras_variants if var))

        # Special promo and product mappings
        promo_mappings = {
            'cbl bundle promo': 'Commander Legends: Battle for Baldur\'s Gate',
            'treasure chest promo': 'Treasure Chest',
            'ikoria: extras': 'ikoria: lair of behemoths',
            'znr: extras': 'zendikar rising',
            'afr extras': 'adventures in the forgotten realms',
            'promos: miscellaneous': 'Judge Gift Cards',
            'brawl deck exclusive': 'Commander Collection',
            'brawl': 'Commander Collection',
            'the list': 'Mystery Booster: The List',
            'set boosters reserved list': 'Mystery Booster: The List'
        }

        # Handle catalog numbers first
        catalog_match = re.match(r'#\d+\s*-\s*(.*)', name_lower)
        if catalog_match:
            cleaned_catalog = catalog_match.group(1).strip()
            if cleaned_catalog in promo_mappings:
                normalized = promo_mappings[cleaned_catalog]
                return [name_lower, cleaned_catalog, normalized, normalized.lower()]
        
        # Direct promo mapping check
        if name_lower in promo_mappings:
            normalized = promo_mappings[name_lower]
            return [name_lower, normalized, normalized.lower()]

        # Enhanced patterns for numbered editions and catalog numbers
        patterns_to_clean = [
            (r'#\d+\s*-\s*', ''),           # Remove "#159 - " style prefixes
            (r'\s*M\d+\s*$', ''),           # Remove "M58" style suffixes
            (r'\(\d+\)\s*', ''),            # Remove "(16) " style prefixes
            (r'\s+', ' '),                   # Normalize multiple spaces
        ]

        # Apply cleanup patterns
        cleaned_name = name_lower
        for pattern, replacement in patterns_to_clean:
            cleaned_name = re.sub(pattern, replacement, cleaned_name)
        cleaned_name = cleaned_name.strip()
        
        # Add both original and cleaned versions to results
        results = [name_lower, cleaned_name]

        # Extra normalization patterns for numbered editions
        edition_patterns = {
            r'(\d+)(th|rd|nd|st) edition': lambda m: f'{m.group(1)}ed',
            r'#\d+ - ': '',  # Remove catalog numbers
            r'\(\d+\)': '',  # Remove parenthetical numbers
        }

        # Common set name mappings
        set_mappings = {
            # D&D Universe sets
            'adventures in the forgotten realms': [
                'afr',
                'afr extras',
                'afr: extras',
                'afr:extras',
                'forgotten realms',
                'd&d',
                'dungeons & dragons'
            ],
            
            # Zendikar sets
            'zendikar rising': [
                'znr',
                'znr extras',
                'znr: extras',
                'znr:extras',
                'zendikar',
                'zendikar rising extras'
            ],
            
            # Other Modern Sets with Extras
            'innistrad midnight hunt': [
                'mid',
                'mid extras',
                'mid: extras',
                'mid:extras'
            ],
            'innistrad crimson vow': [
                'vow',
                'vow extras',
                'vow: extras',
                'vow:extras'
            ],
            'kamigawa neon dynasty': [
                'neo',
                'neo extras',
                'neo: extras',
                'neo:extras'
            ],
            
            # Lord of the Rings sets
            'tales of middle-earth': ['ltr', 'lotr', 'lord of the rings', 'middle earth'],
            
            # D&D Universe sets - separated by specific set
            'commander legends: battle for baldurs gate': ['clb', 'baldurs gate', 'baldur\'s gate'],
            'commander legends': ['cmr'],  # Original Commander Legends
            # Mystery Booster variants
            'mystery booster': ['mb1'],
            'mystery booster: the list': ['the list', 'set boosters reserved list'],
            
            # Promotional sets
            'promotional': ['promo'],
            'judge gift cards': ['j', 'judge', 'judge gift', 'promos: miscellaneous'],
            'pre-release promos': ['pr', 'prerelease', 'pre-release'],
            
            # Special products
            'commander collection': ['cc1', 'cc2'],
            'modern event deck': ['md1'],
            
            # Expeditions/Special sets
            'zendikar expeditions': ['exp', 'zne'],
            'masterpiece series': ['mps'],
            
            # Universe Beyond
            'universes beyond': ['ub'],
            'warhammer 40,000': ['40k', 'warhammer 40k'],
            'doctor who': ['who', 'dr who', 'dr. who'],
            
            # Standard sets
            'kaldheim': ['khm'],
            'origins': ['ori']
        }

        # Additional prefixes to remove
        prefixes = [
            'promo pack:', 'promo packs:', 
            'commander:', 'commander ',
            'token:', 'tokens:', 
            'minigame:', 'minigames:',
            'art series:', 'art cards:',
            'promos:', 'promo:', 
            'extras:', 'extra:',
            'box:', 'box set:',
            'game day:', 'gameday:',
            'prerelease:', 'pre-release:',
            'release:', 'release event:',
            'buy-a-box:', 'bundle:', 
            'media:', 'media insert:',
            'universes beyond:', 'universe beyond:',
            'singles:', 'singles',
            'non-foil:', 'non-foil',
            'foil:', 'foil',
            'mps:', 'judge rewards:',
            'unique & misc:', 'unique and misc:',
            'modern event deck:',
            'battle for zendikar:',
            'extended art:',
            '- extended art',
            'commander: universe beyond:',
            'commander: universes beyond:',
        ]

        # Apply edition pattern replacements
        normalized = name_lower
        for pattern, replacement in edition_patterns.items():
            if callable(replacement):
                normalized = re.sub(pattern, replacement, normalized)
            else:
                normalized = re.sub(pattern, replacement, normalized)
        results.append(normalized)

        # Apply set mappings
        for base, variants in set_mappings.items():
            if base in name_lower:
                results.extend(variants)
                # Also add combinations with prefixes removed
                for variant in variants:
                    results.append(f"commander {variant}")
                    results.append(f"universe beyond {variant}")
                    results.append(f"universes beyond {variant}")

        # Remove prefixes and add results
        for prefix in prefixes:
            if name_lower.startswith(prefix):
                clean_name = name_lower.replace(prefix, '').strip()
                results.append(clean_name)

        # Add general cleanup variations
        results.extend([
            name_lower.replace(':', '').strip(),
            name_lower.replace('  ', ' ').strip(),
            ''.join(name_lower.split()),
            ' '.join(name_lower.split()),
            name_lower.replace('-', ' ').strip(),
            name_lower.replace('_', ' ').strip(),
            name_lower.replace(',', '').strip(),
            name_lower.replace('(', '').replace(')', '').strip(),
        ])

        # Remove duplicates and empty strings
        return list(set(result for result in results if result))

    @classmethod
    def get_set_code(cls, set_name):
        """Get set code from set name using exact match first, then fuzzy matching"""
        if not set_name:
            logger.warning("Empty set name provided")
            return "unknown"  # Default fallback

        logger.debug(f"Getting set code for: {set_name}")
        
        sets_data = cls.get_sets_data()
        if not sets_data:
            logger.error("No sets data available")
            return "unknown"  # Default fallback

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
                if (norm_name == set_info["name"].lower() or 
                    norm_name == set_info["code"].lower()):
                    logger.debug(f"Exact match found against name/code for '{set_name}'")
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
                    score_cutoff=70,    # Lower threshold
                    limit=1
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
        return "unknown"  # Default fallback when no match found

    @classmethod
    def get_closest_set_name(cls, unclean_set_name):
        """Get the official set name from an unclean set name input.
        
        Args:
            unclean_set_name (str): The potentially messy set name to clean
            
        Returns:
            str: The official set name if found, or the original name if no match
        """
        if not unclean_set_name:
            return None

        sets_data = cls.get_sets_data()
        if not sets_data:
            return unclean_set_name

        # Get normalized versions of the set name
        normalized_names = cls._normalize_set_name(unclean_set_name)
        
        # Try exact matches first
        for norm_name in normalized_names:
            # Check against cached set names
            for set_info in sets_data.values():
                if norm_name == set_info["name"].lower():
                    return set_info["name"]  # Return the official name

        # If no exact match, try fuzzy matching
        try:
            best_match = process.extractOne(
                unclean_set_name.lower(),
                [s["name"].lower() for s in sets_data.values()],
                scorer=fuzz.token_set_ratio,
                score_cutoff=75
            )
            
            if best_match:
                matched_name = best_match[0]
                # Find and return the official name (with proper capitalization)
                for set_info in sets_data.values():
                    if set_info["name"].lower() == matched_name:
                        return set_info["name"]
                        
        except Exception as e:
            logger.error(f"Error during fuzzy matching of set name: {str(e)}")

        # Check for "promo" in the name and match against promo sets
        if "promo" in unclean_set_name.lower():
            for set_info in sets_data.values():
                if set_info["set_type"] == "promo":
                    return set_info["name"]

        return unclean_set_name  # Return original if no match found

    @classmethod
    def get_clean_set_code(cls, unclean_set_name):
        """Get the official set code from an unclean set name input.
        
        Args:
            unclean_set_name (str): The potentially messy set name to clean
            
        Returns:
            str: The official set code if found, or 'unknown' if no match
        """
        # First get the proper set name
        clean_set_name = cls.get_closest_set_name(unclean_set_name)
        if not clean_set_name:
            return 'unknown'

        # Then get the set code using the existing method
        return cls.get_set_code(clean_set_name)
    
    @classmethod
    def _find_full_set_name(cls, code):
        """Find full set name from a set code."""
        # Common set code to full name mappings
        known_sets = {
            'znr': 'zendikar rising',
            'afr': 'adventures in the forgotten realms',
            'neo': 'kamigawa neon dynasty',
            'dmu': 'dominaria united',
            'one': 'phyrexia all will be one',
            'mom': 'march of the machine',
            'ltr': 'lord of the rings',
            'bro': 'the brothers war',
            'woe': 'wilds of eldraine',
            'lci': 'lost caverns of ixalan',
            'mkm': 'murders at karlov manor',
            'who': 'doctor who',
            'mat': 'march of the machine aftermath',
            'mid': 'innistrad midnight hunt',
            'vow': 'innistrad crimson vow',
            'snc': 'streets of new capenna',
            'ncc': 'new capenna commander',
            'clb': 'commander legends battle for baldurs gate',
            '40k': 'warhammer 40000',
            'dmc': 'dominaria united commander',
            'brc': 'brother\'s war commander',
            # Add more as needed
        }
        return known_sets.get(code.lower())

    @classmethod
    def _get_all_set_variants(cls, set_name):
        """Get all possible variants of a set name including extras versions."""
        variants = []
        name_lower = set_name.lower()
        
        # Base variants
        variants.extend([
            name_lower,
            name_lower.replace(' ', ''),
            name_lower.replace(':', ''),
            name_lower.replace(':', ' '),
        ])
        
        # Add extras variants
        extras_variants = [
            f"{name_lower} extras",
            f"{name_lower}: extras",
            f"{name_lower}:extras",
        ]
        variants.extend(extras_variants)
        
        # If it's a known set code, add full name variants
        full_name = cls._find_full_set_name(name_lower)
        if full_name:
            full_variants = [
                full_name,
                f"{full_name} extras",
                f"{full_name}: extras",
                full_name.replace(' ', ''),
                full_name.replace(':', ''),
            ]
            variants.extend(full_variants)
        
        # Remove duplicates and empty strings
        return list(set(v for v in variants if v))
    # Card Operations
    @staticmethod
    def get_user_buylist_cards():
        return UserBuylistCard.query.all()
    
    @staticmethod
    def get_user_buylist_card_by_id(card_id):
        """
        Get a specific card from the user's buylist by ID.
        """
        return Card.query.filter_by(id=card_id).first()
    
    @staticmethod
    def add_user_buylist_card(card_id=None, name=None, set_name=None, language="English", quantity=1, version="Standard", foil=False, buylist_id=None, user_id=None):
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
                    set_code = CardService.get_clean_set_code(set_name)
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
                        set_code=set_code,
                        set_name=set_name,
                        language=language,
                        quantity=quantity,
                        version=version,
                        foil=foil,
                        buylist_id=buylist_id,
                        user_id=user_id
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
                current_app.logger.error(f"Card {card_id} not found")
                return None

            # Update card attributes
            card.name = data.get("name", card.name)
            card.set_code = data.get("set_code", card.set_code)
            card.set_name = data.get("set_name", card.set_name)
            card.language = data.get("language", card.language)
            card.quantity = data.get("quantity", card.quantity)
            card.version = data.get("version", card.version)
            card.foil = data.get("foil", card.foil)
            card.buylist_name = data.get("buylist_name", card.buylist_name)  # Add this line

            current_app.logger.info(f"Updated card data: {card.to_dict()}")
            db.session.commit()

            return card
        except Exception as e:
            current_app.logger.error(f"Error updating card: {str(e)}")
            db.session.rollback()
            raise
    
    @staticmethod
    def get_all_buylists(user_id):
        """Get all saved buylists for a specific user."""
        try:
            buylists = UserBuylistCard.query.with_entities(UserBuylistCard.buylist_id, UserBuylistCard.buylist_name).filter_by(user_id=user_id).distinct().all()
            return [{"buylist_id": buylist[0], "buylist_name": buylist[1]} for buylist in buylists]
        except Exception as e:
            logger.error(f"Error fetching buylists: {str(e)}")
            raise

    @staticmethod
    def save_buylist(buylist_id, buylist_name, user_id, cards):
        """Save a new buylist or update an existing one."""
        try:
            with CardService.transaction_context():
                buylist = UserBuylistCard.query.filter_by(buylist_id=buylist_id, user_id=user_id).first()
                if buylist:
                    # Update existing buylist
                    buylist.cards = cards
                    db.session.add(buylist)  # Ensure the buylist is added to the session
                else:
                    # Create new buylist
                    max_buylist_id = db.session.query(db.func.max(UserBuylistCard.buylist_id)).filter_by(user_id=user_id).scalar() or 0
                    new_buylist_id = max_buylist_id + 1
                    for card in cards:
                        new_card = UserBuylistCard(
                            name=card['name'],
                            set_code=card.get('set_code'),
                            set_name=card.get('set_name'),
                            language=card.get('language', 'English'),
                            quantity=card.get('quantity', 1),
                            version=card.get('version', 'Standard'),
                            foil=card.get('foil', False),
                            buylist_id=new_buylist_id,
                            buylist_name=buylist_name,
                            user_id=user_id
                        )
                        db.session.add(new_card)  # Ensure each new card is added to the session
                db.session.commit()  # Commit the session after adding all cards
                return buylist or new_card
        except Exception as e:
            logger.error(f"Error saving buylist: {str(e)}")
            db.session.rollback()
            raise

    @staticmethod
    def get_buylist_by_id(buylist_id):
        """Get a saved buylist by ID."""
        try:
            return UserBuylistCard.query.get(buylist_id)
        except Exception as e:
            logger.error(f"Error fetching buylist: {str(e)}")
            raise

    @staticmethod
    def get_buylist_by_name(buylist_name):
        """Get a saved buylist by name."""
        try:
            return UserBuylistCard.query.filter_by(buylist_name=buylist_name).all()
        except Exception as e:
            logger.error(f"Error fetching buylist: {str(e)}")
            raise

    @staticmethod
    def get_buylist_cards_by_id(buylist_id):
        """Get all cards for a specific buylist by ID."""
        try:
            return UserBuylistCard.query.filter_by(buylist_id=buylist_id).all()
        except Exception as e:
            logger.error(f"Error fetching buylist cards: {str(e)}")
            raise

    @staticmethod
    def get_top_buylists(user_id, limit=3):
        """Get the top 'limit' buylists for a specific user."""
        try:
            buylists = UserBuylistCard.query\
                .with_entities(
                    UserBuylistCard.buylist_id,
                    UserBuylistCard.buylist_name
                )\
                .filter_by(user_id=user_id)\
                .distinct()\
                .limit(limit)\
                .all()
            return [{"buylist_id": b.buylist_id, "buylist_name": b.buylist_name} for b in buylists]
        except Exception as e:
            logger.error(f"Error fetching top buylists: {str(e)}")
            raise

    # Scryfall section
    @staticmethod
    def fetch_scryfall_data(card_name, set_code=None, language=None, version=None):
        current_app.logger.info(f"Fetching Scryfall data for: {card_name} (set: {set_code})")
        
        try:
            # First try exact match with set
            params = {
                'exact': card_name,
                'set': set_code if set_code else None,
                'lang': language if language else 'en'
            }
            # Remove None values
            params = {k: v for k, v in params.items() if v is not None}

            current_app.logger.info(f"Making exact request to Scryfall with params: {params}")
            response = requests.get(SCRYFALL_API_NAMED_URL, params=params)
            
            if response.status_code != 200:
                # If exact match fails, try fuzzy search
                current_app.logger.info("Exact match failed, trying fuzzy search")
                params['fuzzy'] = card_name
                del params['exact']
                response = requests.get(SCRYFALL_API_NAMED_URL, params=params)
                
                if response.status_code != 200:
                    current_app.logger.error(f"Scryfall API error: {response.text}")
                    return None

            card_data = response.json()
            current_app.logger.info(f"Successfully retrieved card data for: {card_name} (set: {set_code})")

            # Fetch all printings
            all_printings = []
            if prints_uri := card_data.get('prints_search_uri'):
                prints_response = requests.get(prints_uri)
                if prints_response.status_code == 200:
                    prints_data = prints_response.json()
                    all_printings = [{
                        'id': print_data.get('id'),
                        'name': print_data.get('name'),
                        'set_code': print_data.get('set'),
                        'set_name': print_data.get('set_name'),
                        'collector_number': print_data.get('collector_number'),
                        'rarity': print_data.get('rarity'),
                        'image_uris': print_data.get('image_uris', {}),
                        'prices': print_data.get('prices', {}),
                        'digital': print_data.get('digital', False),
                        'lang': print_data.get('lang', 'en')
                    } for print_data in prints_data.get('data', [])]

            result = {
                'scryfall': {
                    **card_data,
                    'all_printings': all_printings
                },
                'scan_timestamp': datetime.now().isoformat()
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
     
    @staticmethod
    def fetch_all_printings(prints_search_uri):
        all_printings = []
        next_page = prints_search_uri

        while next_page:
            try:
                response = requests.get(next_page)
                response.raise_for_status()
            except requests.exceptions.RequestException as e:
                current_app.logger.error(f"Error fetching printings data from Scryfall: {str(e)}")
                return []

            data = response.json()
            current_app.logger.debug(f"Scryfall all printings data for page: {data}")

            for card in data.get('data', []):
                current_app.logger.debug(f"Processing card printing: {card}")
                all_printings.append({
                    'set_code': card.get('set'),
                    'set_name': card.get('set_name'),
                    'rarity': card.get('rarity'),
                    'collector_number': card.get('collector_number'),
                    'prices': card.get('prices'),
                    'scryfall_uri': card.get('scryfall_uri'),
                    'image_uris': card.get('image_uris')  # Include image_uris for hover previews
                })

            next_page = data.get('next_page')

        return all_printings

    @staticmethod
    def get_card_suggestions(query, limit=20):
        scryfall_api_url = f"{SCRYFALL_API_BASE}/catalog/card-names"
        try:
            response = requests.get(scryfall_api_url)
            response.raise_for_status()
            all_card_names = response.json()["data"]
            # Filter card names based on the query
            suggestions = [
                name for name in all_card_names if query.lower() in name.lower()
            ]
            return suggestions[:limit]  # Return only up to the limit
        except requests.RequestException as e:
            logger.error(
                "Error fetching card suggestions from Scryfall: %s", str(e))
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
                    site_id = store.get('site_id')
                    cards = store.get('cards', [])

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
                    site_method = site.method.lower() if hasattr(site, 'method') else ''
                    
                    if site_method in ['crystal', 'scrapper']:
                        payload = {
                            "authenticity_token": "Dwn7IuTOGRMC6ekxD8lNnJWrsg45BVs85YplhjuFzbM=",
                            "query": "\n".join(card.get("name", "") for card in cards if card.get("name")),
                            "submit": "Continue",
                        }
                        purchase_url = site.url
                    elif site_method == 'shopify':
                        card_names = [card.get("name", "") for card in cards if card.get("name")]
                        purchase_url, payload = CardService.create_shopify_url_and_payload(site, card_names)
                    elif site_method == 'hawk':
                        purchase_url, payload = CardService.create_hawk_url_and_payload(site, cards)
                    else:
                        logger.warning(f"Unsupported purchase method '{site_method}' for site ID {site_id}.")
                        continue

                    # Add the result
                    results.append({
                        "site_name": store.get('site_name', f'Unknown Site {site_id}'),
                        "site_id": site_id,
                        "purchase_url": purchase_url,
                        "payload": payload,
                        "method": site_method,
                        "country": getattr(site, 'country', 'Unknown'),
                        "cards": cards,
                        "card_count": len(cards),
                    })

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
            
            # Construct API URL
            api_url = "https://api.binderpos.com/external/shopify/decklist"
            if hasattr(site, 'api_url') and site.api_url:
                api_url += f"?storeUrl={site.api_url}&type=mtg"
            
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
                "ClientData": {
                    "VisitorId": str(uuid.uuid4())
                },
                "ClientGuid": "30c874915d164f71bf6f84f594bf623f",
                "FacetSelections": {
                    "tab": ["Magic"],
                    "child_inventory_level": ["1"]
                },
                "query": query,
                "SortBy": "score"
            }
            
            json_payload = json.dumps(payload)
            return api_url, json_payload
        except Exception as e:
            logger.error(f"Error creating Shopify request for {site.name}: {str(e)}")
            return None