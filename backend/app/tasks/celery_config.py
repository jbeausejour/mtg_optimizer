import os

class CeleryConfig:
    # Get the absolute path to the project root
    PROJECT_ROOT = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
    
    # # Define the instance path
    INSTANCE_PATH = os.path.join(PROJECT_ROOT, 'backend', 'instance')
    
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

    @staticmethod
    def as_dict():
        return {key: value for key, value in CeleryConfig.__dict__.items() 
                if not key.startswith('__') and not callable(value)}