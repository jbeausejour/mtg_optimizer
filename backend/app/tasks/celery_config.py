import os

from celery.schedules import crontab
from datetime import timedelta


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
    imports = [
        "app.tasks.optimization_tasks",
        "app.tasks.watchlist_tasks",  # Add watchlist tasks
    ]

    task_track_started = True
    task_time_limit = 30 * 60  # 30 minutes

    worker_hijack_root_logger = True
    worker_redirect_stdouts = True
    worker_redirect_stdouts_level = "INFO"
    worker_log_color = False
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
        # NEW: Watchlist tasks
        "watchlist-check-prices": {
            "task": "watchlist.check_all_prices",
            "schedule": timedelta(minutes=30),  # Every 30 minutes
            "args": (1, False),  # max_age_hours=1, force_check=False
            "options": {
                "queue": "watchlist",
                "expires": 1500,  # Expire after 25 minutes
            },
        },
        "watchlist-update-mtgstocks": {
            "task": "watchlist.update_mtgstocks_prices",
            "schedule": timedelta(hours=2),  # Every 2 hours
            "args": (5,),  # batch_size=5
            "options": {
                "queue": "watchlist",
                "expires": 7200,  # Expire after 2 hours
            },
        },
        "watchlist-cleanup-alerts": {
            "task": "watchlist.cleanup_old_alerts",
            "schedule": crontab(hour=3, minute=30),  # Daily at 3:30 AM
            "args": (30,),  # days_to_keep=30
            "options": {
                "queue": "watchlist",
                "expires": 86400,  # Expire after 24 hours
            },
        },
        "watchlist-daily-full-check": {
            "task": "watchlist.check_all_prices",
            "schedule": crontab(hour=2, minute=0),  # Daily at 2 AM
            "args": (24, True),  # max_age_hours=24, force_check=True
            "options": {
                "queue": "watchlist",
                "expires": 21600,  # Expire after 6 hours
            },
        },
        "watchlist-health-check": {
            "task": "watchlist.health_check",
            "schedule": timedelta(minutes=15),  # Every 15 minutes
            "options": {
                "queue": "watchlist",
                "expires": 900,  # 15 minutes
            },
        },
    }

    task_routes = {
        "app.tasks.optimization_tasks.scrape_site_task": {"queue": "main"},
        "app.tasks.optimization_tasks.start_scraping_task": {"queue": "main"},
        "app.tasks.optimization_tasks.refresh_scryfall_cache": {"queue": "main"},
        "watchlist.check_all_prices": {"queue": "watchlist"},
        "watchlist.check_single_item": {"queue": "watchlist"},
        "watchlist.cleanup_old_alerts": {"queue": "watchlist"},
        "watchlist.update_mtgstocks_prices": {"queue": "watchlist"},
        "watchlist.manual_check_user_watchlist": {"queue": "watchlist"},
        "watchlist.health_check": {"queue": "watchlist"},
    }
    task_annotations = {
        "watchlist.check_all_prices": {
            "rate_limit": "1/m",  # Max 1 per minute
        },
        "watchlist.update_mtgstocks_prices": {
            "rate_limit": "1/h",  # Max 1 per hour
        },
        "watchlist.check_single_item": {
            "rate_limit": "30/m",  # Max 30 per minute
        },
        "watchlist.manual_check_user_watchlist": {
            "rate_limit": "10/m",  # Max 10 per minute
        },
    }

    @staticmethod
    def as_dict():
        return {
            key: value
            for key, value in CeleryConfig.__dict__.items()
            if not key.startswith("__") and not callable(value)
        }
