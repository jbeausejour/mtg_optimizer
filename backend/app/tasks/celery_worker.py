import logging
from flask import Flask
from app import create_app
from app.tasks.celery_app import celery_app
from .celery_config import CeleryConfig

# Configure basic console logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    force=True
)

# logger = logging.getLogger('celery_worker_logger')
logger = logging.getLogger(__name__)

# Create Flask app and push context
app = create_app()
app.app_context().push()

# Initialize Celery with updated config
celery_app.conf.update(app.config)
celery_app.conf.update(
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=10
)

logger.info("Flask app created and context pushed")
logger.info(f"Celery broker URL: {celery_app.conf.broker_url}")
logger.info(f"Celery result backend: {celery_app.conf.result_backend}")

if __name__ == "__main__":
    with app.app_context():
        print("Starting Celery worker...")
        celery_app.worker_main(["worker", "--loglevel=info", "--pool=solo"])
