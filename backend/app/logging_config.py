import logging
import os
from logging.handlers import RotatingFileHandler

from colorama import Fore, init

# Initialize colorama for Windows compatibility
init(autoreset=True)


class ColoredFormatter(logging.Formatter):
    LEVEL_COLORS = {
        "DEBUG": Fore.BLUE,
        "INFO": Fore.WHITE,
        "WARNING": Fore.YELLOW,
        "ERROR": Fore.RED,
        "CRITICAL": Fore.RED,
    }

    def format(self, record):
        color = self.LEVEL_COLORS.get(record.levelname, Fore.WHITE)
        record.levelname = f"{color}{record.levelname}{Fore.RESET}"
        return super().format(record)


def setup_logging(log_filename="logs/app.log", add_pid=False):
    """Configure logging to use both console and file handlers with colors."""
    if not os.path.exists("logs"):
        os.makedirs("logs")

    if add_pid:
        base, ext = os.path.splitext(log_filename)
        log_filename = f"{base}_{os.getpid()}{ext}"

    # Create handlers
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(ColoredFormatter("[%(name)s:%(lineno)d] - %(message)s"))

    file_handler = RotatingFileHandler(log_filename, maxBytes=5 * 1024 * 1024, backupCount=10, delay=True)
    file_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s [%(name)s:%(lineno)d]"))

    return console_handler, file_handler
