import logging
from typing import Optional, Dict, Any, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user_buylist_card import UserBuylistCard
from app.models.buylist import UserBuylist
from app.services.async_base_service import AsyncBaseService

logger = logging.getLogger(__name__)


class UserBuylistCardService(AsyncBaseService[UserBuylistCard]):
    model_class = UserBuylistCard

    @classmethod
    async def get_all_user_buylist_cards(cls, session: AsyncSession, user_id: int) -> List[UserBuylistCard]:
        """Get all cards for a specific user"""
        try:
            result = await session.execute(select(UserBuylistCard).filter(UserBuylistCard.user_id == user_id))
            return [item.to_dict() for item in result.scalars().all()]
        except Exception as e:
            logger.error(f"Error fetching all user buylist cards: {str(e)}")
            return []

    @classmethod
    async def get_buylist_cards_by_id(cls, session: AsyncSession, id: int) -> List[UserBuylistCard]:
        """Get all cards for a specific buylist by ID."""
        try:
            result = await session.execute(select(UserBuylistCard).filter(UserBuylistCard.buylist_id == id))
            return [item.to_dict() for item in result.scalars().all()]
        except Exception as e:
            logger.error(f"Error fetching buylist cards: {str(e)}")
            raise

    ##########################
    # Add / Update
    ##########################
    @classmethod
    async def add_cards_to_buylist(
        cls, session: AsyncSession, id: int, user_id: int, cards_data: List[Dict[str, Any]]
    ) -> UserBuylist:
        """
        Adds cards to a buylist, preventing duplicates.
        """
        try:
            # Verify buylist exists and belongs to user
            result = await session.execute(
                select(UserBuylist).filter(UserBuylist.id == id, UserBuylist.user_id == user_id)
            )
            buylist = result.scalars().first()

            if not buylist:
                raise ValueError("Buylist does not exist.")

            if not cards_data:
                raise ValueError("No cards provided.")

            # Get existing cards in the buylist
            cards_result = await session.execute(select(UserBuylistCard).filter(UserBuylistCard.buylist_id == id))
            existing_cards = {c.name.lower() for c in cards_result.scalars().all()}

            for card in cards_data:
                card_name = card["name"].strip().lower()
                if card_name in existing_cards:
                    continue  # Skip duplicate cards

                await cls.create(
                    session,
                    **{
                        "user_id": user_id,
                        "buylist_id": id,
                        "name": card["name"],
                        "set_name": card.get("set_name"),
                        "set_code": card.get("set_code"),
                        "language": card.get("language", "English"),
                        "quantity": card.get("quantity", 1),
                        "quality": card.get("quality", "NM"),
                        "version": card.get("version", "Standard"),
                        "foil": card.get("foil", False),
                    },
                )

            # Refresh the buylist to include the new cards
            result = await session.execute(
                select(UserBuylist).filter(UserBuylist.id == id, UserBuylist.user_id == user_id)
            )
            updated_buylist = result.scalars().first()

            return updated_buylist.to_dict()
        except Exception as e:
            logger.error(f"Error adding cards to buylist: {str(e)}")
            raise

    @classmethod
    async def add_user_buylist_card(
        cls,
        session: AsyncSession,
        name: str,
        buylist_id: int,
        user_id: int,
        set_name: Optional[str] = None,
        language: str = "English",
        quality: str = "NM",
        quantity: int = 1,
        version: str = "Standard",
        foil: bool = False,
        card_id: Optional[int] = None,
    ):
        """Save a new card or update an existing card with proper validation and error handling"""
        try:
            if not name:
                raise ValueError("Card name is required")
            if quantity < 1:
                raise ValueError("Quantity must be positive")

            # Get set code if set_name is provided
            set_code = None
            if set_name:
                # In async context, we should use an async method to get set code
                # Assuming you have or will create this method
                set_code = await cls.get_clean_set_code_from_set_name(session, set_name)
                if not set_code:
                    raise ValueError(f"Invalid set name: {set_name}")
                logger.info(f"Mapped set name '{set_name}' to code '{set_code}'")

            if card_id:
                # Get existing card
                result = await session.execute(select(UserBuylistCard).filter(UserBuylistCard.id == card_id))
                card = result.scalars().first()

                if not card:
                    raise ValueError(f"Card with ID {card_id} not found")

                # Update card
                card.name = name
                card.set_code = set_code
                card.set_name = set_name
                card.language = language
                card.quantity = quantity
                card.quality = quality
                card.version = version
                card.foil = foil
                card.buylist_id = buylist_id
                card.user_id = user_id

                return card.to_dict()
            else:
                new_card = await cls.create(
                    session,
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
                return new_card.to_dict()

        except Exception as e:
            logger.error(f"Error saving card: {str(e)}")
            raise

    @classmethod
    async def update_user_buylist_card(
        cls, session: AsyncSession, card_id: int, user_id: int, data: Dict[str, Any]
    ) -> Optional[UserBuylistCard]:
        """Update a specific card in the user's buylist."""
        try:
            logger.info(f"Updating card {card_id} with data: {data}")

            # Get the card
            result = await session.execute(select(UserBuylistCard).filter(UserBuylistCard.id == card_id))
            card = result.scalars().first()

            if not card:
                return None

            buylist_id = data.get("buylist_id")
            if not buylist_id:
                raise ValueError("Buylist ID is required")

            # Verify buylist exists and belongs to user
            buylist_result = await session.execute(
                select(UserBuylist).filter(UserBuylist.id == buylist_id, UserBuylist.user_id == user_id)
            )
            buylist = buylist_result.scalars().first()

            if not buylist:
                raise ValueError("Buylist does not exist")

            if card.buylist_id != buylist_id:
                raise ValueError("Card does not belong to the provided buylist")

            # Update the card using AsyncBaseService
            await cls.update(session, card, data)

            return card.to_dict()
        except Exception as e:
            logger.error(f"Error updating card: {str(e)}")
            raise

    ##########################
    # Delete
    ##########################
    @classmethod
    async def delete_card_from_buylist(
        cls, session: AsyncSession, buylist_id: int, card_name: str, quantity: int, user_id: int
    ) -> bool:
        """
        Deletes a card from the specified buylist.
        """
        try:
            result = await session.execute(
                select(UserBuylistCard).filter(
                    UserBuylistCard.buylist_id == buylist_id,
                    UserBuylistCard.name == card_name,
                    UserBuylistCard.user_id == user_id,
                )
            )
            card = result.scalars().first()

            if not card:
                logger.warning(f"Card '{card_name}' not found in buylist ID {buylist_id}.")
                return False

            if card.quantity > quantity:
                card.quantity -= quantity
                logger.info(
                    f"Reduced quantity of '{card_name}' in buylist ID {buylist_id} by {quantity}. Remaining: {card.quantity}."
                )
            else:
                await cls.delete(session, card)
                logger.info(f"Deleted '{card_name}' from buylist ID {buylist_id}.")

            return True

        except Exception as e:
            logger.error(f"Error deleting card '{card_name}' from buylist ID {buylist_id}: {str(e)}")
            return False
