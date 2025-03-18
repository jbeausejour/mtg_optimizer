import logging

from app.logging_config import setup_logging
from app.tasks.celery_instance import celery_app

# Apply logging setup
for logger_name in [__name__, "celery"]:
    logger = logging.getLogger(logger_name)
    if not logger.handlers:
        console_handler, file_handler = setup_logging("logs/celery_app.log")
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False

# Define task_logger explicitly
task_logger = logging.getLogger("celery")
task_logger.info(f"Celery app initialized with broker: {celery_app.conf.broker_url}")
