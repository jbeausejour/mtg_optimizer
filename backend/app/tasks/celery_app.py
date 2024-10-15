import logging
import os
from celery import Celery
from .celery_config import CeleryConfig

logger = logging.getLogger("celery_task_logger")
logger.setLevel(logging.INFO)

if not logger.hasHandlers():
    # Add console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]"))
    logger.addHandler(console_handler)

    # Optional: File handler for persistent logging
    if not os.path.exists("logs"):
        os.makedirs("logs")

    file_handler = logging.handlers.RotatingFileHandler(
        "logs/celery_tasks.log", maxBytes=10240, backupCount=10
    )
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]")
    )
    logger.addHandler(file_handler)

def make_celery(app=None):
    celery = Celery(
        app.import_name if app else "mtg_optimizer",
        broker=CeleryConfig.broker_url,
        backend=CeleryConfig.result_backend,
        include=["app.tasks.optimization_tasks"],
    )
    
    # Get Celery's internal logger and attach the same handlers
    celery_logger = logging.getLogger("celery")
    if not celery_logger.hasHandlers():
        celery_logger.setLevel(logging.INFO)
        celery_logger.addHandler(console_handler)
        celery_logger.addHandler(file_handler)
    logger.info(f"Celery app created with broker: {celery.conf.broker_url}")
    return celery


celery_app = make_celery()


def init_celery(app):
    celery_app.conf.update(app.config)
    logger.info("Celery initialized with Flask app config")

    class ContextTask(celery_app.Task):
        def __call__(self, *args, **kwargs):
            if app is not None:
                with app.app_context():
                    return self.run(*args, **kwargs)
            return self.run(*args, **kwargs)

    celery_app.Task = ContextTask
    app.extensions["celery"] = celery_app

    logger.info("ContextTask set for Celery")
    return celery_app
