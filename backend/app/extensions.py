from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate
from flask_rq2 import RQ
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
cors = CORS(resources={r"/api/*": {"origins": "*"}})
rq = RQ()
limiter = Limiter(key_func=get_remote_address,
                  storage_uri="redis://localhost:6379/0")


def init_extensions(app):
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    cors.init_app(app)
    rq.init_app(app)
    limiter.init_app(app)
