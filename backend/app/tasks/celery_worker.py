from app import create_app
from celery_app import make_celery

app = create_app()
celery = make_celery(app)