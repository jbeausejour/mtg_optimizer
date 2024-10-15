import logging

import os 
from logging.handlers import RotatingFileHandler

def get_logger(name): 
    """Configure and return a logger for use in modules.""" 
    logger = logging.getLogger(name) 
    logger.setLevel(logging.INFO)
    if not logger.hasHandlers():
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]")
        )
        logger.addHandler(console_handler)

        # Optional: File handler
        if not os.path.exists("logs"):
            os.makedirs("logs")

        file_handler = RotatingFileHandler(
            f"logs/{name}.log", maxBytes=10240, backupCount=10
        )
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]")
        )
        logger.addHandler(file_handler)

    return logger

