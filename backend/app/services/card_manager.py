# backend/app/services/card_manager.py
import logging
from datetime import datetime, timezone

from mtgsdk import Card
from app.extensions import db
from app.models.card import UserBuylistCard, MarketplaceCard
from app.models.sets import Sets

logger = logging.getLogger(__name__)

class CardManager:
    @staticmethod
    def fetch_card_data(card_name, set_code=None, language=None, version=None):
        try:
            cards = Card.where(name=card_name).all()
            if set_code:
                cards = [card for card in cards if card.set.lower() == set_code.lower()]
            if language:
                cards = [card for card in cards if card.language.lower() == language.lower()]

            if not cards:
                logger.error(f"Card '{card_name}' not found.")
                return None

            return {
                "scryfall": cards[0].to_dict(),
                "scan_timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"Error fetching card data for '{card_name}': {str(e)}")
            return None

    @staticmethod
    def get_user_buylist_cards():
        return UserBuylistCard.query.all()

    @staticmethod
    def add_card_to_buylist(card_data):
        # Simplified example for adding a card to buylist
        new_card = UserBuylistCard(**card_data)
        db.session.add(new_card)
        db.session.commit()
        return new_card

    @staticmethod
    def fetch_all_sets():
        # Fetch sets from database (can use Scryfall or mtgsdk if necessary)
        return Sets.query.order_by(Sets.released_at.desc()).all()

