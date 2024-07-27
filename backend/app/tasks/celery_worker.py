import os
import sys

# Get the absolute path of the current file
current_path = os.path.abspath(os.path.dirname(__file__))

# Add the parent directory of 'app' to the Python path
project_root = os.path.abspath(os.path.join(current_path, '..', '..'))
sys.path.insert(0, project_root)

from app import create_app
from app.tasks.celery_app import make_celery

app = create_app()
celery = make_celery(app)

# Debug prints
print(f"Project root: {project_root}")
print(f"Python path: {sys.path}")
print(f"Current working directory: {os.getcwd()}")

# Ensure all tasks are imported
import app.tasks.optimization_tasks

if __name__ == '__main__':
    print("Starting Celery worker...")
    print(f"Celery Broker URL: {celery.conf.broker_url}")
    print(f"Celery Result Backend: {celery.conf.result_backend}")
    celery.start()