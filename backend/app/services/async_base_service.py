import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import TypeVar, Generic, Type, Optional, List, Any, Dict, Union

# Type variable for model classes
T = TypeVar("T")

logger = logging.getLogger(__name__)


class AsyncBaseService(Generic[T]):
    """Base service with common database operations for async SQLAlchemy."""

    model_class: Type[T] = None

    @classmethod
    async def get_by_id(cls, session: AsyncSession, model_id: int) -> Optional[T]:
        """Get a model instance by ID."""
        try:
            result = await session.execute(select(cls.model_class).where(cls.model_class.id == model_id))
            return result.scalars().first()
        except Exception as e:
            logger.error(f"Error in get_by_id for {cls.model_class.__name__}: {str(e)}")
            raise

    @classmethod
    async def get_all(cls, session: AsyncSession) -> List[T]:
        """Get all instances of the model."""
        try:
            result = await session.execute(select(cls.model_class))
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error in get_all for {cls.model_class.__name__}: {str(e)}")
            raise

    @classmethod
    async def create(cls, session: AsyncSession, **kwargs) -> T:
        """Create a new instance of the model."""
        try:
            instance = cls.model_class(**kwargs)
            session.add(instance)
            await session.flush()  # Flush to get the ID without committing
            await session.refresh(instance)
            return instance
        except Exception as e:
            logger.error(f"Error in create for {cls.model_class.__name__}: {str(e)}")
            raise

    @classmethod
    async def update(cls, session: AsyncSession, instance: T, updates: Dict[str, Any]) -> T:
        """
        Update an existing instance of the model with the provided fields.
        """
        try:
            for key, value in updates.items():
                setattr(instance, key, value)
            await session.flush()
            return instance
        except Exception as e:
            logger.error(f"Error in update for {cls.model_class.__name__}: {str(e)}")
            raise

    @classmethod
    async def delete(cls, session: AsyncSession, obj: T):
        """Delete a record."""
        try:
            await session.delete(obj)
        except Exception as e:
            logger.error(f"Error in delete for {cls.model_class.__name__}: {str(e)}")
            raise

    @classmethod
    async def filter_by(cls, session: AsyncSession, **kwargs) -> List[T]:
        """Filter by provided attributes."""
        try:
            conditions = []
            for key, value in kwargs.items():
                if hasattr(cls.model_class, key):
                    conditions.append(getattr(cls.model_class, key) == value)

            if not conditions:
                return []

            result = await session.execute(select(cls.model_class).where(*conditions))
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error in filter_by for {cls.model_class.__name__}: {str(e)}")
            raise
