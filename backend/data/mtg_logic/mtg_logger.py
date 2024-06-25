import logging

# Setup logger
logger = logging.getLogger('mtg_logger')
logger.setLevel(logging.DEBUG)

# Create file handler
fh = logging.FileHandler('mtg_debug.log')
fh.setLevel(logging.DEBUG)

# Create console handler
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

# Create formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
ch.setFormatter(formatter)

# Add the handlers to the logger
logger.addHandler(fh)
logger.addHandler(ch)

def get_logger():
    return logger
