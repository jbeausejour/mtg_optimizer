from .celery_app import celery_app as celery_app
from .celery_app import make_celery
from .celery_config import CeleryConfig
from .optimization_tasks import optimize_cards, cleanup_old_scans, test_task, start_scraping_task

# Define what should be imported when "from app.tasks import *" is used
__all__ = [
    'celery_app',
    'make_celery',
    'CeleryConfig',
    'optimize_cards',
    'cleanup_old_scans',
    'start_scraping_task',
    'test_task'
]