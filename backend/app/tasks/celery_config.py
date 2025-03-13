import os

class CeleryConfig:
    # Get the absolute path to the project root
    PROJECT_ROOT = os.path.abspath(
        os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.dirname(__file__))))
    )

    # # Define the instance path
    INSTANCE_PATH = os.path.join(PROJECT_ROOT, "backend", "instance")

    # Celery Configuration using SQLite
    # broker_url = "redis://127.0.0.1:6379/0"
    # result_backend = "redis://127.0.0.1:6379/0"
    broker_url = "redis://192.168.68.15:6379/0"
    result_backend = "redis://192.168.68.15:6379/0"

    # Add these lines
    broker_connection_max_retries = 10  # Retry up to 10 times
    broker_pool_limit = None  # Disable connection pooling
    broker_connection_retry_on_startup = True
    broker_transport_options = {"visibility_timeout": 3600, 'socket_timeout': 10.0, 'socket_connect_timeout': 10.0}  # 1 hour.
    imports = ["app.tasks.optimization_tasks"]

    task_track_started = True
    task_time_limit = 30 * 60  # 30 minutes
    worker_hijack_root_logger = False  # Don't hijack the root logger    
    worker_redirect_stdouts = True  # Redirect stdout/stderr to the Celery logger
    worker_redirect_stdouts_level = "INFO"  # Ensure all standard output is logged

    # Logging configuration
    worker_log_format = "%(asctime)s - %(message)s"
    worker_task_log_format = "%(asctime)s - %(task_name)s - %(message)s"

    task_serializer = "json"
    result_serializer = "json"
    accept_content = ["json"]
    timezone = "UTC"
    enable_utc = True
    result_expires = 300 # Results expire after 1 hour

    worker_concurrency = 20
    worker_pool = 'solo'

    @staticmethod
    def as_dict():
        return {
            key: value
            for key, value in CeleryConfig.__dict__.items()
            if not key.startswith("__") and not callable(value)
        }
