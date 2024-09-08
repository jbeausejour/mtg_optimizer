import os
import sys
import logging
from app import create_app
from app.tasks.celery_app import celery_app


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Get the absolute path of the current file
current_path = os.path.abspath(os.path.dirname(__file__))

# Add the parent directory of 'app' to the Python path
project_root = os.path.abspath(os.path.join(current_path, '..'))
sys.path.insert(0, project_root)

app = create_app()
app.app_context().push()

logger.info("Flask app created and context pushed")
logger.info(f"Celery broker URL: {celery_app.conf.broker_url}")
logger.info(f"Celery result backend: {celery_app.conf.result_backend}")

if __name__ == '__main__':
    with app.app_context():
        print("Starting Celery worker...")
        celery_app.worker_main(['worker', '--loglevel=info --pool=solo'])