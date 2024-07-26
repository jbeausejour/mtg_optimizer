import os
import sys

# Add the project root directory to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from app import create_app
from app.tasks.celery_app import make_celery

app = create_app()
celery = make_celery(app)

# Ensure all tasks are imported
import app.tasks.optimization_tasks

if __name__ == '__main__':
    celery.start()