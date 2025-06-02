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

    model_class = Settings

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
    async def get_setting_by_key(cls, session: AsyncSession, key: str) -> Optional[Settings]:
        """Get a specific setting by key"""
        try:
            stmt = select(Settings).where(Settings.key == key)
            result = await session.execute(stmt)
            return result.scalars().first()
        except Exception as e:
            logger.error(f"Error fetching setting '{key}': {str(e)}")
            raise

    @classmethod
    async def update_setting(cls, session: AsyncSession, key: str, value: str) -> Settings:
        """Update or create a setting"""
        try:
            existing_setting = await cls.get_setting_by_key(session, key)
            if existing_setting:
                existing_setting.value = str(value)
                await session.flush()  # Only flush, don't commit
                logger.info(f"Updated setting '{key}' to '{value}'")
                return existing_setting
            else:
                setting = await cls.create(session, key=key, value=str(value))
                await session.flush()  # Only flush
                logger.info(f"Created new setting '{key}' with value '{value}'")
                return setting
        except Exception as e:
            logger.error(f"Error updating setting '{key}': {str(e)}")
            await session.rollback()
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
