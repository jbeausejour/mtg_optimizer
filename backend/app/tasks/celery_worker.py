import logging
import os
import sys

from app import create_app
from app.tasks.celery_app import celery_app


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("celery_worker_logger")

# Configure a file handler for the worker log
if not os.path.exists("logs"):
    os.makedirs("logs")

file_handler = logging.handlers.RotatingFileHandler(
    "logs/celery_worker.log", maxBytes=10240, backupCount=10
)
file_handler.setFormatter(
    logging.Formatter("%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]")
)
logger.addHandler(file_handler)

# Add a stream handler for console output
console_handler = logging.StreamHandler()
console_handler.setFormatter(
    logging.Formatter("%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]")
)
logger.addHandler(console_handler)

# Get the absolute path of the current file
current_path = os.path.abspath(os.path.dirname(__file__))

# Add the parent directory of 'app' to the Python path
project_root = os.path.abspath(os.path.join(current_path, ".."))
sys.path.insert(0, project_root)

app = create_app()
app.app_context().push()

logger.info("Flask app created and context pushed")
logger.info(f"Celery broker URL: {celery_app.conf.broker_url}")
logger.info(f"Celery result backend: {celery_app.conf.result_backend}")

if __name__ == "__main__":
    with app.app_context():
        print("Starting Celery worker...")
        celery_app.worker_main(["worker", "--loglevel=info --pool=solo"])
