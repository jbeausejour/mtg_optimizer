import os
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

# Use environment variable or default for CORS
cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:3000")
if "," in cors_origins:
    cors_origins = cors_origins.split(",")
    print(f"CORS origins set to: {cors_origins}")
else:
    print(f"CORS origin set to: {cors_origins}")

# Initialize CORS with more permissive settings for debugging
cors = CORS(
    resources={r"/api/*": {"origins": cors_origins}},
    supports_credentials=True,
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
)

# Use environment variable or default for Redis
redis_url = os.environ.get("REDIS_URL", "redis://192.168.68.15:6379/0")
redis_host = os.environ.get("REDIS_HOST", "192.168.68.15")
rq = RQ(redis_url=redis_url)
limiter = Limiter(key_func=get_remote_address, storage_uri=redis_url)


def init_extensions(app):
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    cors.init_app(app)
    rq.init_app(app)
    limiter.init_app(app)
