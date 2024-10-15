import logging
import os
import sys
import time

from celery.exceptions import TimeoutError
from flask import current_app

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Add the project root directory to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

from app import create_app
from app.tasks.celery_app import celery_app
from app.tasks.optimization_tasks import test_task


def setup_app():
    app = create_app()
    app.app_context().push()
    return app


def test_simple_task():
    current_app.logger.info("Sending test task")
    result = test_task.delay()
    current_app.logger.info(f"Test task ID: {result.id}")
    try:
        task_result = result.get(timeout=10)
        current_app.logger.info(f"Test task result: {task_result}")
    except TimeoutError:
        current_app.logger.error("Test task timed out")
    except Exception as e:
        current_app.logger.error(f"Error occurred: {str(e)}")


if __name__ == "__main__":
    app = setup_app()
    current_app.logger.info("Testing simple task:")
    test_simple_task()
