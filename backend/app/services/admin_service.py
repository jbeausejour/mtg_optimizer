import logging
from contextlib import contextmanager

from app.extensions import db
from app.models.settings import Settings
from flask import current_app
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


class AdminService:

    @contextmanager
    def transaction_context():
        """Context manager for database transactions"""
        try:
            yield
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Database error: {str(e)}")
            raise
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error in transaction: {str(e)}")
            raise
        finally:
            db.session.close()

    # Settings Operations
    @staticmethod
    def get_setting(key):
        return Settings.query.filter_by(key=key).first()

    @staticmethod
    def update_setting(key, value):
        setting = Settings.query.filter_by(key=key).first()
        if setting:
            setting.value = value
        else:
            setting = Settings(key=key, value=value)
            db.session.add(setting)
        db.session.commit()
        return setting

    @staticmethod
    def get_all_settings():
        return Settings.query.all()
