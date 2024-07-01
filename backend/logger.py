import logging
from logging.handlers import RotatingFileHandler

def setup_logging(app):
    if app.debug:
        app.logger.setLevel(logging.DEBUG)
    else:
        file_handler = RotatingFileHandler('logs/myapp.log', maxBytes=10240, backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)

    app.logger.info('Mtg Optimizer startup')