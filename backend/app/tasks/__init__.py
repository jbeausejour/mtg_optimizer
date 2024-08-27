from .celery_app import make_celery
from .celery_config import CeleryConfig
from .optimization_tasks import optimize_cards, cleanup_old_scans, test_task

# Define what should be imported when "from app.tasks import *" is used
__all__ = [
    'make_celery',
    'CeleryConfig',
    'optimize_cards',
    'cleanup_old_scans',
    'test_task'
]

# Optional: Initialize Celery instance if needed
# from flask import current_app
# celery = make_celery(current_app)