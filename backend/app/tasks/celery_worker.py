import asyncio
import logging

from app import create_app
from app.logging_config import setup_logging
from app.tasks.celery_instance import celery_app

logger = logging.getLogger("celery_worker")
if not logger.handlers:
    console_handler, file_handler = setup_logging("logs/celery_worker.log")
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


async def start_worker():
    app = create_app()

    async with app.app_context():
        logger.info("Quart app created and async context pushed")
        logger.info(f"Celery broker URL: {celery_app.conf.broker_url}")
        logger.info(f"Celery result backend: {celery_app.conf.result_backend}")

        # Start celery (synchronously)
        celery_app.start(["worker", "--loglevel=info"])
        # celery_app.start(["worker", "--loglevel=info", "--pool=solo"])


if __name__ == "__main__":
    print("Starting Celery worker with async context...")
    asyncio.run(start_worker())
