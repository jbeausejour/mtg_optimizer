from app.tasks.celery_config import CeleryConfig
from celery import Celery

celery_app = Celery(
    "mtg_optimizer",
    broker=CeleryConfig.broker_url,
    backend=CeleryConfig.result_backend,
    include=["app.tasks.optimization_tasks"],
)

celery_app.config_from_object(CeleryConfig)  # Load Celery configuration
