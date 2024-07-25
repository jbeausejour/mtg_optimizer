from app import create_app
from app.tasks.celery_app import make_celery

app = create_app()
app.app_context().push()  # Push the application context

celery = make_celery(app)

if __name__ == '__main__':
    celery.start()