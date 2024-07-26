from celery import Celery, Task
from app.tasks import celery_config

def make_celery(app):

    class ContextTask(Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
            
    celery = Celery()
    celery.config_from_object(celery_config.CeleryConfig)
    celery.Task = ContextTask
    
    return celery

