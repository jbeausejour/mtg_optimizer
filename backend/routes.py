from views import views
import logging

logger = logging.getLogger(__name__)

def register_blueprints(app):
    # Register Blueprints
    app.register_blueprint(views, url_prefix='/api/v1')
    logger.debug("Blueprint 'views' registered with prefix '/api/v1'")
    print("Blueprint 'views' registered with prefix '/api/v1'")
