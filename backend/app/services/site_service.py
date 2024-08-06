from app.models.site import Site

class MarketplaceManager:
    @staticmethod
    def get_all_sites():
        return Site.query.all()
