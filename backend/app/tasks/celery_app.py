import logging

from celery import Celery

from .celery_config import CeleryConfig

logger = logging.getLogger(__name__)


def make_celery(app=None):
    celery = Celery(
        app.import_name if app else "mtg_optimizer",
        broker=CeleryConfig.broker_url,
        backend=CeleryConfig.result_backend,
        include=["app.tasks.optimization_tasks"],
    )
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
