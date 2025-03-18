from app.tasks.celery_config import CeleryConfig
from app.tasks.celery_instance import celery_app
from app.tasks.optimization_tasks import refresh_scryfall_cache, start_scraping_task

# Define what should be imported when "from app.tasks import *" is used
__all__ = [
    "celery_app",
    "CeleryConfig",
    "start_scraping_task",
    "refresh_scryfall_cache",
]
