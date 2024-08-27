from app.models.site import Site
from app.extensions import db
from sqlalchemy.exc import IntegrityError

class MarketplaceManager:
    @staticmethod
    def get_all_sites():
        return Site.query.all()
    
    @staticmethod
    def add_site(data):
        new_site = Site(**data)
        db.session.add(new_site)
        db.session.commit()
        return new_site

    @staticmethod
    def update_site(site_id, data):
        site = Site.query.get(site_id)
        if not site:
            raise ValueError("Site not found")

        changes_made = False
        for key, value in data.items():
            if hasattr(site, key) and getattr(site, key) != value:
                setattr(site, key, value)
                changes_made = True

        if changes_made:
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                raise ValueError("Update failed due to integrity constraint")
        else:
            raise ValueError("No changes detected")

        return site

    @staticmethod
    def get_site(site_id):
        site = Site.query.get(site_id)
        if not site:
            raise ValueError("Site not found")
        return site