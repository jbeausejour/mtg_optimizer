import logging

def configure_logger(filename, log_level_file, log_level_console):
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    fh = logging.FileHandler(filename)
    fh.setLevel(log_level_file)

    ch = logging.StreamHandler()
    ch.setLevel(log_level_console)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    logger.addHandler(fh)
    logger.addHandler(ch)

    return logger
