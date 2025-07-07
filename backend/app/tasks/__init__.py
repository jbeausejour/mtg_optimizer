from app.tasks.celery_config import CeleryConfig
from app.tasks.celery_instance import celery_app
from app.tasks.optimization_tasks import refresh_scryfall_cache, start_scraping_task
from app.tasks.watchlist_tasks import (
    check_all_watchlist_prices,
    check_single_watchlist_item,
    cleanup_old_price_alerts,
    update_mtgstocks_prices_for_watchlist,
    manual_check_user_watchlist,
)

# Define what should be imported when "from app.tasks import *" is used
__all__ = [
    "celery_app",
    "CeleryConfig",
    "start_scraping_task",
    "refresh_scryfall_cache",
    "check_all_watchlist_prices",
    "check_single_watchlist_item",
    "cleanup_old_price_alerts",
    "update_mtgstocks_prices_for_watchlist",
    "manual_check_user_watchlist",
]
