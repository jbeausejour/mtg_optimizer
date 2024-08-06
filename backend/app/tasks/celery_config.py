import os

class CeleryConfig:
    # Get the absolute path to the project root
    PROJECT_ROOT = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
    
    # # Define the instance path
    INSTANCE_PATH = os.path.join(PROJECT_ROOT, 'backend', 'instance')

    # broker_connection_retry = True
    # broker_connection_max_retries = 5


    # broker_url = f"sqla+sqlite:///{os.path.join(INSTANCE_PATH, 'celery-broker.sqlite').replace('\\', '/')}"
    # result_backend = f"db+sqlite:///{os.path.join(INSTANCE_PATH, 'celery-results.sqlite').replace('\\', '/')}"
    
    # Celery Configuration using SQLite
    broker_url = 'redis://localhost:6379/0'
    result_backend = 'redis://localhost:6379/0'
    imports = ['app.tasks.optimization_tasks']
    
    broker_connection_retry_on_startup = True
    task_serializer = 'json'
    result_serializer = 'json'
    accept_content = ['json']
    timezone = 'UTC'
    enable_utc = True

    # print(f"Celery Broker URL: {broker_url}")
    # print(f"Celery Result Backend: {result_backend}")
    # print(f"Instance Path: {INSTANCE_PATH}")

    @classmethod
    def as_dict(cls):
        return {key: value for key, value in cls.__dict__.items() 
                if not key.startswith('__') and not callable(value)}

    @classmethod
    def init_app(cls, app):
        app.config.update(
            CELERY_broker_url=cls.broker_url,
            result_backend=cls.result_backend
        )