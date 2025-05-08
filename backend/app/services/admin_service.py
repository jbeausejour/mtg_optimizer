import logging
from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.settings import Settings
from app.models.user import User
from app.services.async_base_service import AsyncBaseService

logger = logging.getLogger(__name__)


class AdminService(AsyncBaseService):
    """Async service for admin operations"""

    @classmethod
    async def get_setting(cls, session: AsyncSession, key: str) -> Optional[Settings]:
        """Get a setting by key"""
        try:
            result = await session.execute(select(Settings).filter(Settings.key == key))
            return result.scalars().first()
        except Exception as e:
            logger.error(f"Error getting setting '{key}': {str(e)}")
            raise

    @classmethod
    async def update_setting(cls, session: AsyncSession, key: str, value: str) -> Settings:
        """Update or create a setting"""
        try:
            # Check if setting exists
            setting = await cls.get_setting(session, key)

            if setting:
                # Update existing setting
                await cls.update(session, setting, {"value": value})
            else:
                # Create new setting
                setting = await cls.create(session, key=key, value=value)

            return setting
        except Exception as e:
            logger.error(f"Error updating setting '{key}': {str(e)}")
            raise

    @classmethod
    async def get_all_settings(cls, session: AsyncSession) -> List[Settings]:
        """Get all settings"""
        try:
            result = await session.execute(select(Settings))
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting all settings: {str(e)}")
            raise

    @classmethod
    async def create_user(cls, session: AsyncSession, username: str, email: str, password: str) -> User:
        """Create a new user and return the instance"""
        # username = "Julz"
        # email = "jules.beausejour@gmail.com"
        # password = "Julz"
        try:
            user = User(username=username, email=email)
            user.set_password(password)

            created_user = await cls.create(session, user)
            return created_user
        except Exception as e:
            logger.error(f"Error creating user '{username}': {str(e)}")
            raise
