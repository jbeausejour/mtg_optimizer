from flask import Blueprint
from views import views

def register_blueprints(app):
    # Register Blueprints
    app.register_blueprint(views)
