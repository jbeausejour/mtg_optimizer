import asyncio
import logging
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


# This module provides async context managers for managing resources like aiohttp sessions and network drivers.
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
        yield driver
    except Exception as e:
        logger.error(f"Error in network driver: {str(e)}")
        raise
    finally:
        if driver:
            try:
                logger.debug(f"Closing network driver: {id(driver)}")
                await driver.close()
                logger.debug(f"Closed network driver: {id(driver)}")
            except Exception as e:
                logger.error(f"Error closing network driver: {str(e)}")


@asynccontextmanager
async def create_event_loop():
    """Creates a new event loop and closes it when done.

    Yields:
        The created event loop
    """
    loop = None
    try:
        # Create new event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        logger.debug(f"Created new event loop: {id(loop)}")
        yield loop
    finally:
        if loop:
            try:
                # Close the loop when done
                pending = asyncio.all_tasks(loop)
                if pending:
                    logger.warning(f"Cancelling {len(pending)} pending tasks before closing loop")
                    for task in pending:
                        task.cancel()
                    await asyncio.gather(*pending, return_exceptions=True)

                loop.run_until_complete(loop.shutdown_asyncgens())
                loop.run_until_complete(loop.shutdown_default_executor())
                loop.close()
                logger.debug(f"Closed event loop: {id(loop)}")
            except Exception as e:
                logger.error(f"Error closing event loop: {str(e)}")
            finally:
                # Reset event loop policy
                asyncio.set_event_loop(None)
