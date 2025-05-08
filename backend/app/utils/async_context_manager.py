import asyncio
import logging
import os
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

logger = logging.getLogger(__name__)

# This module provides async context managers for managing resources like aiohttp sessions and network drivers.

# ENGINE IS CREATED ONCE when the worker starts
async_engine_celery = create_async_engine(
    os.environ.get("SQLALCHEMY_DATABASE_URI"),
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=5,  # Or adjust for your concurrency needs
)

# SESSIONMAKER IS CREATED ONCE
async_session_factory_celery = async_sessionmaker(
    bind=async_engine_celery,
    expire_on_commit=False,
)
# ENGINE IS CREATED ONCE when the worker starts
async_engine_flask = create_async_engine(
    os.environ.get("SQLALCHEMY_DATABASE_URI"),
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=5,  # Or adjust for your concurrency needs
)

# SESSIONMAKER IS CREATED ONCE
async_session_factory_flask = async_sessionmaker(
    bind=async_engine_flask,
    expire_on_commit=False,
)


def get_celery_session_factory():
    return async_session_factory_celery


def get_flask_session_factory():
    return async_session_factory_flask


@asynccontextmanager
async def celery_session_scope():
    """Async context manager for Celery session usage."""
    async with async_session_factory_celery() as session:
        async with session.begin():  # <-- BEGIN a transaction automatically
            try:
                yield session
            finally:
                await session.close()


@asynccontextmanager
async def flask_session_scope():
    """Async context manager for Celery session usage."""
    async with async_session_factory_flask() as session:
        async with session.begin():  # <-- BEGIN a transaction automatically
            try:
                yield session
            finally:
                await session.close()


@asynccontextmanager
async def managed_aiohttp_session(session_factory, name="unnamed"):
    """Context manager to ensure proper cleanup of aiohttp sessions.

    Args:
        session_factory: A callable that returns an aiohttp.ClientSession
        name: A name for logging purposes

    Yields:
        The created session
    """
    session = None
    try:
        session = session_factory()
        logger.debug(f"Created session {name}: {id(session)}")
        yield session
    except Exception as e:
        logger.error(f"Error in session {name}: {str(e)}")
        raise
    finally:
        if session and not session.closed:
            try:
                logger.debug(f"Closing session {name}: {id(session)}")
                await session.close()
                # Add a small sleep to ensure all connections are closed
                await asyncio.sleep(0.25)
                logger.debug(f"Closed session {name}: {id(session)}")
            except Exception as e:
                logger.error(f"Error closing session {name}: {str(e)}")


@asynccontextmanager
async def managed_network_driver(driver_factory):
    """Context manager to ensure proper cleanup of NetworkDriver instances.

    Args:
        driver_factory: A callable that returns a NetworkDriver

    Yields:
        The created NetworkDriver
    """
    driver = None
    try:
        driver = driver_factory()
        logger.debug(f"Created network driver: {id(driver)}")

        # Initialize the session if it's not already initialized
        if hasattr(driver, "_ensure_session"):
            await driver._ensure_session()

        yield driver
    except Exception as e:
        logger.error(f"Error in network driver: {str(e)}")
        raise
    finally:
        if driver:
            try:
                logger.debug(f"Closing network driver: {id(driver)}")
                await driver.close()
                logger.debug(f"Network driver closed: {id(driver)}")
            except Exception as e:
                logger.error(f"Error closing network driver: {str(e)}")
