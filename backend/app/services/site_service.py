from app.models.site import Site

def get_all_sites():
    return Site.query.all()
