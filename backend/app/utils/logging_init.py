import logging

def init_logging():
    """Initialize logging with console-only output"""
    # Remove all existing handlers
    root = logging.getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)
            
    # Configure basic console logging with reduced duplicates
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(message)s',
        force=True,
        handlers=[logging.StreamHandler()]
    )
    
    # Prevent duplicate logs
    logging.getLogger('celery').propagate = False
    logging.getLogger('celery.task').propagate = False
    logging.getLogger('app.utils.data_fetcher').propagate = False
    
    # Set lower level for some loggers
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)
    logging.getLogger('aiohttp').setLevel(logging.WARNING)

    # Configure root logger to reduce duplicates
    root.setLevel(logging.WARNING)