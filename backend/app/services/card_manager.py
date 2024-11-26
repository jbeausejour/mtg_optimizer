from datetime import datetime
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from app.extensions import db
from app.models.card import UserBuylistCard
from app.models.scan import Scan
from app.models.site import Site
from app.models.settings import Settings
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

class CardManager:
    
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
            cards = Card.where(name=card_name).all()
            if set_code:
                cards = [card for card in cards if card.set.lower() == set_code.lower()]
            if language:
                cards = [card for card in cards if card.language.lower() == language.lower()]

            if not cards:
                pass
                return None
            
            data = CardManager.fetch_scryfall_data(card_name, set_code, language, version)
            return data
        except Exception as e:
            current_app.logger.debug(f"Error fetching card data for '{card_name}': {str(e)}")
            return None

    @staticmethod
    def save_card(card_id=None, name=None, set=None, language="English", quantity=1, version="Standard", foil=False):
        """Save a new card or update an existing card with proper validation and error handling"""
        try:
            with CardManager.transaction_context():
                if not name:
                    raise ValueError("Card name is required")
                
                if quantity < 1:
                    raise ValueError("Quantity must be positive")

                if card_id:
                    card = UserBuylistCard.query.get(card_id)
                    if not card:
                        raise ValueError(f"Card with ID {card_id} not found")
                    
                    card.name = name
                    card.set = set
                    card.language = language
                    card.quantity = quantity
                    card.version = version
                    card.foil = foil
                else:
                    card = UserBuylistCard(
                        name=name,
                        set=set,
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
        """
        Update a specific card in the user's buylist.
        """
        # Fetch the card by ID using the correct model
        card = UserBuylistCard.query.get(card_id)
        if not card:
            return None

        # Update card attributes
        card.name = data.get("name", card.name)
        card.set = data.get("set", card.set)
        card.language = data.get("language", card.language)
        card.quantity = data.get("quantity", card.quantity)
        card.version = data.get("version", card.version)
        card.foil = data.get("foil", card.foil)

        # Commit changes to the database
        db.session.commit()

        return card
    
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
        params = {'exact': card_name}
        if set_code:
            params['set'] = set_code
        if language:
            params['lang'] = language

        response = requests.get(SCRYFALL_API_NAMED_URL, params=params)
        if response.status_code == 200:
            card_data = response.json()
        else:
            # If exact match fails, try fuzzy search
            params['fuzzy'] = card_name
            del params['exact']
            response = requests.get(SCRYFALL_API_NAMED_URL, params=params)

            if response.status_code == 200:
                card_data = response.json()
            else:
                # If both searches fail, return None
                return None

                # If version is specified, find the matching version
        if version and 'all_parts' in card_data:
            for part in card_data['all_parts']:
                if part['component'] == 'combo_piece' and fuzz.ratio(part.get('name', ''), version) > 90:
                    response = requests.get(part['uri'])
                    if response.status_code == 200:
                        card_data = response.json()
                    break

        # Fetch all printings
        all_printings = []
        if 'prints_search_uri' in card_data:
            all_printings = CardManager.fetch_all_printings(card_data['prints_search_uri'])

        # Return the card data including all printings
        return {
            'scryfall': {
                **card_data,  # Unpack the original Scryfall response
                'all_printings': all_printings  # Add the all_printings key
            },
            'scan_timestamp': datetime.now().isoformat()
        }
    
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

    # Marketplace Site Operations
    @staticmethod
    def get_all_sites():
        return Site.query.all()

    @staticmethod
    def add_site(data):
        new_site = Site(**data)
        db.session.add(new_site)
        db.session.commit()
        return new_site

    @staticmethod
    def update_site(site_id, data):
        site = Site.query.get(site_id)
        if not site:
            raise ValueError("Site not found")

        changes_made = False
        for key, value in data.items():
            if hasattr(site, key) and getattr(site, key) != value:
                setattr(site, key, value)
                changes_made = True

        if changes_made:
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                raise ValueError("Update failed due to integrity constraint")
        else:
            raise ValueError("No changes detected")

        return site

    # Scan Operations
    @staticmethod
    def get_scan_results(scan_id):
        return Scan.query.get_or_404(scan_id)

    @staticmethod
    def get_all_scan_results(limit=5):
        return Scan.query.order_by(Scan.created_at.desc()).limit(limit).all()

    # Settings Operations
    @staticmethod
    def get_setting(key):
        return Settings.query.filter_by(key=key).first()

    @staticmethod
    def update_setting(key, value):
        setting = Settings.query.filter_by(key=key).first()
        if setting:
            setting.value = value
        else:
            setting = Settings(key=key, value=value)
            db.session.add(setting)
        db.session.commit()
        return setting