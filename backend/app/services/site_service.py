from app.models.site import Site

class SiteService:
    @staticmethod
    def get_all_sites():
        return Site.query.all()
