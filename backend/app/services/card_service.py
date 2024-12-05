from datetime import datetime
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from app.extensions import db
from app.models.card import UserBuylistCard
from app.models.scan import Scan
from app.models.site import Site
from mtgsdk import Card, Set
import logging
import requests
from fuzzywuzzy import fuzz
from flask import current_app
from contextlib import contextmanager

logger = logging.getLogger(__name__)

SCRYFALL_API_BASE = "https://api.scryfall.com"
SCRYFALL_API_NAMED_URL = f"{SCRYFALL_API_BASE}/cards/named"
SCRYFALL_API_SEARCH_URL = f"{SCRYFALL_API_BASE}/cards/search"
CARDCONDUIT_URL = "https://cardconduit.com/buylist"

class CardService:
    
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
    def fetch_card_data(card_name, set_code=None, language=None, version=None):
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
    def save_card(card_id=None, name=None, set_code=None, language="English", quantity=1, version="Standard", foil=False):
        """Save a new card or update an existing card with proper validation and error handling"""
        try:
            with CardService.transaction_context():
                if not name:
                    raise ValueError("Card name is required")
                
                if quantity < 1:
                    raise ValueError("Quantity must be positive")

                if card_id:
                    card = UserBuylistCard.query.get(card_id)
                    if not card:
                        raise ValueError(f"Card with ID {card_id} not found")
                    
                    card.name = name
                    card.set_code = set_code
                    card.language = language
                    card.quantity = quantity
                    card.version = version
                    card.foil = foil
                else:
                    card = UserBuylistCard(
                        name=name,
                        set_code=set_code,
                        language=language,
                        quantity=quantity,
                        version=version,
                        foil=foil,
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
            card.set_code = data.get("set", card.set_code)  # Frontend still sends 'set'
            card.set_name = data.get("set_name", card.set_name)
            card.language = data.get("language", card.language)
            card.quantity = data.get("quantity", card.quantity)
            card.version = data.get("version", card.version)
            card.foil = data.get("foil", card.foil)

            current_app.logger.info(f"Updated card data: {card.to_dict()}")
            db.session.commit()

            return card
        except Exception as e:
            current_app.logger.error(f"Error updating card: {str(e)}")
            db.session.rollback()
            raise
    
    # Set Operations
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
                        'set': print_data.get('set'),
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
                    'set': card.get('set'),
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
