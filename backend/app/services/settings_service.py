from app.models.settings import Settings
from app.extensions import db

class SettingsService:
    @staticmethod
    def get_all_settings():
        return Settings.query.all()

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
    def delete_setting(key):
        setting = Settings.query.filter_by(key=key).first()
        if setting:
            db.session.delete(setting)
            db.session.commit()
            return True
        return False