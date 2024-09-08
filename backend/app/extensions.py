from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_rq2 import RQ

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
cors = CORS()
rq = RQ()

def init_extensions(app):
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    cors.init_app(app)
    rq.init_app(app)