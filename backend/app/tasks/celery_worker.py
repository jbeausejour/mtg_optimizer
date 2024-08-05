import os
import sys
from app import create_app
import app.tasks.optimization_tasks
from app.tasks.celery_app import make_celery
from sqlalchemy import create_engine
from celery.backends.database import SessionManager

# Get the absolute path of the current file
current_path = os.path.abspath(os.path.dirname(__file__))

# Add the parent directory of 'app' to the Python path
project_root = os.path.abspath(os.path.join(current_path, '..', '..'))
sys.path.insert(0, project_root)

app = create_app()
celery = make_celery(app)

# Debug prints
# print(f"Project root: {project_root}")
# print(f"Python path: {sys.path}")
# print(f"Current working directory: {os.getcwd()}")

print("Testing SQLite connections...")

try:
    from sqlalchemy.dialects import sqlite
    broker_engine = create_engine(celery.conf.broker_url)
    broker_engine.connect()
    print(f"Successfully connected to broker SQLite database: {celery.conf.broker_url}")
except ImportError:
    print("SQLite dialect not found. Make sure SQLAlchemy is installed correctly.")
except Exception as e:
    print(f"Failed to connect to broker SQLite: {str(e)}")

try:
    from sqlalchemy.dialects import sqlite
    result_engine = create_engine(celery.conf.result_backend)
    session = SessionManager(result_engine).create_session()
    print(f"Successfully connected to result SQLite database: {celery.conf.result_backend}")
except ImportError:
    print("SQLite dialect not found. Make sure SQLAlchemy is installed correctly.")
except Exception as e:
    print(f"Failed to connect to result SQLite: {str(e)}")


if __name__ == '__main__':
    print("Starting Celery worker...")
    print(f"Celery Broker URL: {celery.conf.broker_url}")
    print(f"Celery Result Backend: {celery.conf.result_backend}")
    celery.start()