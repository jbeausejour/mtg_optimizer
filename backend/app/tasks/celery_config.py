import os

class CeleryConfig:
    # Get the absolute path to the project root
    PROJECT_ROOT = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
    
    # # Define the instance path
    INSTANCE_PATH = os.path.join(PROJECT_ROOT, 'backend', 'instance')
    
    # Celery Configuration using SQLite
    broker_url = 'redis://127.0.0.1:6379/0'
    result_backend = 'redis://127.0.0.1:6379/0'
    
    # Add these lines
    broker_connection_max_retries = None  # Retry indefinitely
    broker_pool_limit = None  # Disable connection pooling
    broker_connection_retry_on_startup = True
    broker_transport_options = {'visibility_timeout': 3600}  # 1 hour.
    imports = ['app.tasks.optimization_tasks']

    
    task_track_started = True
    task_time_limit = 30 * 60  # 30 minutes
    worker_hijack_root_logger = False  # Don't hijack the root logger
    worker_redirect_stdouts = False  # Don't redirect stdout/stderr

    # Logging configuration
    worker_log_format = '[%(asctime)s: %(levelname)s/%(processName)s] %(message)s'
    worker_task_log_format = '[%(asctime)s: %(levelname)s/%(processName)s] [%(task_name)s(%(task_id)s)] %(message)s'

    
    task_serializer = 'json'
    result_serializer = 'json'
    accept_content = ['json']
    timezone = 'UTC'
    enable_utc = True

    @staticmethod
    def as_dict():
        return {key: value for key, value in CeleryConfig.__dict__.items() 
                if not key.startswith('__') and not callable(value)}