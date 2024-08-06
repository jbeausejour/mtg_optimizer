from celery import Celery, Task
from .celery_config import CeleryConfig

def make_celery(app):
    celery = Celery(
        app.import_name,
        broker=CeleryConfig.broker_url,
        backend=CeleryConfig.result_backend
    )
    celery.conf.update(CeleryConfig.as_dict())

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask

    return celery