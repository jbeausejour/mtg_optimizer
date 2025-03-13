import logging
import os
from logging.handlers import RotatingFileHandler
from celery import Celery
from app.tasks.celery_config import CeleryConfig

# Configure loggers
task_logger = logging.getLogger(__name__)
celery_logger = logging.getLogger('celery')

# Color codes
RESET = "\033[0m"
RED = "\033[31m"
YELLOW = "\033[33m"
WHITE = "\033[37m"
BLUE = "\033[34m"

# Formatter for logs with color
class ColoredFormatter(logging.Formatter):
    LEVEL_COLORS = {
        'DEBUG': BLUE,
        'INFO': WHITE,
        'WARNING': YELLOW,
        'ERROR': RED,
        'CRITICAL': RED,
    }

    def format(self, record):
        color = self.LEVEL_COLORS.get(record.levelname, WHITE)
        levelname = f"{color}{record.levelname}{RESET}"
        record.levelname = levelname  # Overwrite the levelname with colored version
        return super().format(record)
    
# Only add handlers if not already configured
if not task_logger.handlers:
    # Console handler with colors
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(ColoredFormatter("%(asctime)s - %(name)s - %(message)s [in %(filename)s:%(lineno)d]"))
    
    # File handler
    if not os.path.exists("logs"):
        os.makedirs("logs")
    file_handler = RotatingFileHandler(
        "logs/celery_tasks.log", maxBytes=10240, backupCount=10
    )
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s: %(message)s [in %(filename)s:%(lineno)d]")
    )
    
    # Add both handlers to both loggers
    for logger in [task_logger, celery_logger]:
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False

def make_celery(app=None):
    celery = Celery(
        app.import_name if app else "mtg_optimizer",
        broker=CeleryConfig.broker_url,
        backend=CeleryConfig.result_backend,
        include=["app.tasks.optimization_tasks"],
    )
    celery.config_from_object(CeleryConfig)  # Apply the full config from celery_config.py

    task_logger.info(f"Celery app created with broker: {celery.conf.broker_url}")
    return celery

celery_app = make_celery()

from celery.schedules import crontab
from app.tasks.optimization_tasks import refresh_scryfall_cache
celery_app.conf.beat_schedule = {
    "refresh_scryfall_cache_daily": {
        "task": "app.tasks.optimization_tasks.refresh_scryfall_cache",
        "schedule": crontab(hour=3, minute=0),  # Run every day at 3 AM
    },
}
# def init_celery(app):
#     celery_app.conf.update(app.config)
#     task_logger.info("Celery initialized with Flask app config")

#     class ContextTask(celery_app.Task):
#         def __call__(self, *args, **kwargs):
#             if app is not None:
#                 with app.app_context():
#                     return self.run(*args, **kwargs)
#             return self.run(*args, **kwargs)

#     celery_app.Task = ContextTask
#     app.extensions["celery"] = celery_app

#     task_logger.info("ContextTask set for Celery")
#     return celery_app
