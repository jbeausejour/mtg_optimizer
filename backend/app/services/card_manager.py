from datetime import datetime
from sqlalchemy.exc import IntegrityError
from app.extensions import db
from app.models.card import UserBuylistCard
from app.models.scan import Scan, ScanResult
from app.models.site import Site
from app.models.settings import Settings
from mtgsdk import Card, Set
import logging

logger = logging.getLogger(__name__)

class CardManager:
    
    # Card Operations
    @staticmethod
    def get_user_buylist_cards():
        return UserBuylistCard.query.all()
    @staticmethod
    def fetch_card_data(card_name, set_code=None, language=None):
        try:
            cards = Card.where(name=card_name).all()
            if set_code:
                cards = [card for card in cards if card.set.lower() == set_code.lower()]
            if language:
                cards = [card for card in cards if card.language.lower() == language.lower()]

            if not cards:
                pass
                return None

            return {
                "scryfall": {
                "name": getattr(cards[0], "name", None),
                "set": getattr(cards[0], "set", None),
                "type": getattr(cards[0], "type", None),
                "rarity": getattr(cards[0], "rarity", None),
                "mana_cost": getattr(cards[0], "mana_cost", None),
                "text": getattr(cards[0], "text", None),
                "flavor": getattr(cards[0], "flavor", None),
                "power": getattr(cards[0], "power", None),
                "toughness": getattr(cards[0], "toughness", None),
                "loyalty": getattr(cards[0], "loyalty", None)
            },
                "scan_timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.debug(f"Error fetching card data for '{card_name}': {str(e)}")
            return None

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
            logger.error(f"Error fetching sets data: {str(e)}")
            return []

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