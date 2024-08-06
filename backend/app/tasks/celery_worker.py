import os
import sys

# Get the absolute path of the current file
current_path = os.path.abspath(os.path.dirname(__file__))

# Add the parent directory of 'app' to the Python path
project_root = os.path.abspath(os.path.join(current_path, '..', '..'))
sys.path.insert(0, project_root)


from app import create_app
from app.tasks.celery_app import make_celery
from app.tasks.optimization_tasks import cleanup_old_scans, optimize_cards, test_task

app = create_app()
celery = make_celery(app)

print("Celery app created")
print(f"Registered tasks: {celery.tasks.keys()}")

if __name__ == '__main__':
    print("Starting Celery worker...")
    print(f"Celery Broker URL: {celery.conf.broker_url}")
    print(f"Celery Result Backend: {celery.conf.result_backend}")
    celery.worker_main(['worker', '--loglevel=debug', '--concurrency=1', '-P', 'solo'])
    #celery.worker_main(['worker', '--loglevel=info','--pool=gevent'])