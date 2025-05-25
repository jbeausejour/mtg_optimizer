import os

from celery.schedules import crontab


class CeleryConfig:
    # Get the absolute path to the project root
    PROJECT_ROOT = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

    # # Define the instance path
    INSTANCE_PATH = os.path.join(PROJECT_ROOT, "backend", "instance")

    # Celery Configuration using SQLite
    # broker_url = "redis://127.0.0.1:6379/0"
    # result_backend = "redis://127.0.0.1:6379/0"

    broker_url = os.environ.get("REDIS_URL", "redis://192.168.68.15:6379/0")
    result_backend = os.environ.get("REDIS_URL", "redis://192.168.68.15:6379/0")
    # broker_url = "redis://192.168.68.15:6379/0"
    # result_backend = "redis://192.168.68.15:6379/0"

    # Add these lines
    broker_connection_max_retries = 10  # Retry up to 10 times
    broker_pool_limit = None  # Disable connection pooling
    broker_connection_retry_on_startup = True
    broker_transport_options = {
        "visibility_timeout": 3600,
        "socket_timeout": 10.0,
        "socket_connect_timeout": 10.0,
    }  # 1 hour.
    imports = ["app.tasks.optimization_tasks"]

    task_track_started = True
    task_time_limit = 30 * 60  # 30 minutes

    worker_hijack_root_logger = True  # Changed to True for prefork
    worker_redirect_stdouts = True  # Redirect stdout/stderr to the Celery logger
    worker_redirect_stdouts_level = "INFO"  # Ensure all standard output is logged
    worker_log_color = False  # Disable color in logs for better file output
    worker_disable_rate_limits = False

    # Logging configuration
    worker_log_format = "%(message)s"
    worker_task_log_format = "%(task_name)s - %(message)s"

    task_serializer = "json"
    result_serializer = "json"
    accept_content = ["json"]
    timezone = "UTC"
    enable_utc = True
    result_expires = 300  # Results expire after 1 hour

    worker_concurrency = 20
    # worker_pool = "solo"
    worker_pool = "prefork"

    # Enable detailed logging
    task_send_sent_event = True
    task_publish_retry = True
    task_publish_retry_policy = {
        "max_retries": 3,
        "interval_start": 0,
        "interval_step": 0.2,
        "interval_max": 0.2,
    }
    beat_schedule = {
        "refresh_scryfall_cache_daily": {
            "task": "app.tasks.optimization_tasks.refresh_scryfall_cache",
            "schedule": crontab(hour=3, minute=0),
        },
    }

    task_routes = {
        "app.tasks.optimization_tasks.scrape_site_task": {"queue": "main"},  # fallback/default queue,
        "app.tasks.optimization_tasks.start_scraping_task": {"queue": "main"},
        "app.tasks.optimization_tasks.refresh_scryfall_cache": {"queue": "main"},
    }

    @staticmethod
    def as_dict():
        return {
            key: value
            for key, value in CeleryConfig.__dict__.items()
            if not key.startswith("__") and not callable(value)
        }
