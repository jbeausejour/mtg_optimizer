from .celery_app import celery_app as celery_app
from .celery_app import make_celery
from .celery_config import CeleryConfig
from .optimization_tasks import start_scraping_task

# Define what should be imported when "from app.tasks import *" is used
__all__ = [
    "celery_app",
    "make_celery",
    "CeleryConfig",
    "start_scraping_task"
]
