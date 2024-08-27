from celery import Celery
from .celery_config import CeleryConfig

def make_celery(app=None):
    celery = Celery(
        'mtg_optimizer',
        broker=CeleryConfig.broker_url,
        backend=CeleryConfig.result_backend,
        include=['app.tasks.optimization_tasks']
    )
    celery.conf.update(CeleryConfig.as_dict())

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            if app is not None:
                with app.app_context():
                    return self.run(*args, **kwargs)
            return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery

# This instance is used by Celery worker to start
celery_app = make_celery()

def init_celery(app):
    celery = make_celery(app)
    celery.conf.update(app.config)
    return celery