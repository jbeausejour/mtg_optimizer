import os
import sys
from dotenv import load_dotenv
from app import create_app
from app.tasks.celery_app import init_celery

# Get the absolute path of the current file
current_path = os.path.abspath(os.path.dirname(__file__))

# Add the parent directory of 'app' to the Python path
project_root = os.path.abspath(os.path.join(current_path, '..'))
sys.path.insert(0, project_root)

app = create_app()
celery = init_celery(app)

if __name__ == '__main__':
    with app.app_context():
        print("Starting Celery worker...")
        print(f"Celery Broker URL: {celery.conf.broker_url}")
        print(f"Celery Result Backend: {celery.conf.result_backend}")
        celery.worker_main(['worker', '--loglevel=info'])