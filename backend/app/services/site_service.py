from app.models.site import Site
from app.extensions import db

class MarketplaceManager:
    @staticmethod
    def get_all_sites():
        return Site.query.all()
    
    @staticmethod
    def add_site(data):
        new_site = Site(
            name=data['name'],
            url=data['url'],
            method=data['method'],
            active=data['active'],
            country=data['country'],
            type=data['type']
        )
        db.session.add(new_site)
        db.session.commit()
        return new_site

    @staticmethod
    def update_site(site_id, data):
        site = Site.query.get(site_id)
        if not site:
            raise ValueError("Site not found")

        site.name = data['name']
        site.url = data['url']
        site.method = data['method']
        site.active = data['active']
        site.country = data['country']
        site.type = data['type']
        
        db.session.commit()
        return site
