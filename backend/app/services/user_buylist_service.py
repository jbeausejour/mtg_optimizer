# New File: buylist_service.py

import logging
from typing import List, Dict, Any
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.buylist import UserBuylist
from app.models.user_buylist_card import UserBuylistCard
from app.services.async_base_service import AsyncBaseService

logger = logging.getLogger(__name__)


class BuylistService(AsyncBaseService[UserBuylist]):
    model_class = UserBuylist

    ##########################
    # Create
    ##########################

    @classmethod
    async def create_buylist(cls, session: AsyncSession, name: str, user_id: int) -> dict:
        try:
            buylist = await cls.create(session, name=name, user_id=user_id)

            # Reload with selectinload to include relationships
            result = await session.execute(
                select(UserBuylist).options(selectinload(UserBuylist.cards)).filter_by(id=buylist.id)
            )
            buylist = result.scalar_one()
            return buylist.to_dict()

        except Exception as e:
            logger.error(f"Error creating buylist: {str(e)}")
            raise

    ##########################
    # Delete
    ##########################
    @classmethod
    async def delete_buylist(cls, session: AsyncSession, id: int, user_id: int) -> bool:
        """
        Deletes a buylist and all associated cards by its ID and user.
        """
        try:
            # Check if the buylist exists
            result = await session.execute(
                select(UserBuylist).filter(UserBuylist.id == id, UserBuylist.user_id == user_id)
            )
            buylist = result.scalars().first()

            if not buylist:
                logger.warning(f"Buylist {id} not found for user {user_id}.")
                return False

            # Delete all associated cards
            await session.execute(
                delete(UserBuylistCard).where(UserBuylistCard.buylist_id == id, UserBuylistCard.user_id == user_id)
            )

            # Delete the buylist itself
            await cls.delete(session, buylist)

            logger.info(f"Buylist {id} and all associated cards deleted successfully.")
            return True
        except Exception as e:
            logger.error(f"Error deleting buylist {id}: {str(e)}")
            return False

    @classmethod
    async def update_user_buylist_name(
        cls, session: AsyncSession, id: int, user_id: int, newbuylist_name: str
    ) -> UserBuylist:
        """Update the name of a specific buylist for a user."""
        try:
            # Find the buylist
            result = await session.execute(
                select(UserBuylist).filter(UserBuylist.id == id, UserBuylist.user_id == user_id)
            )
            buylist = result.scalars().first()

            if not buylist:
                raise ValueError("Buylist does not exist.")

            # Use async_base_service update
            await cls.update(session, buylist, {"name": newbuylist_name})

            logger.info(f"Buylist '{buylist.name}' updated successfully")
            return buylist.to_dict()
        except Exception as e:
            logger.error(f"Error updating buylist name: {str(e)}")
            raise

    @classmethod
    async def get_top_buylists(cls, session: AsyncSession, user_id: int) -> List[Dict[str, Any]]:
        """Get the top buylists for a specific user, sorted by most recently updated."""
        try:
            result = await session.execute(
                select(UserBuylist.id, UserBuylist.name)
                .filter(UserBuylist.user_id == user_id)
                .order_by(UserBuylist.updated_at.desc())
                .limit(3)
            )
            buylists = result.all()
            return [{"id": buylist.id, "name": buylist.name} for buylist in buylists]
        except Exception as e:
            logger.error(f"Error fetching top buylists: {str(e)}")
            raise

    ##########################
    #  Buylist Card Operations
    ##########################
    # Get
    ##########################
    @classmethod
    async def get_all_buylists(cls, session: AsyncSession, user_id: int):
        try:
            result = await session.execute(
                select(UserBuylist)
                .filter(UserBuylist.user_id == user_id)
                .options(selectinload(UserBuylist.cards))  # ✅ this line is key
            )
            buylists = result.scalars().all()
            return [buylist.to_dict() for buylist in buylists]
        except Exception as e:
            logger.error(f"Error fetching buylists: {str(e)}")
            return []
