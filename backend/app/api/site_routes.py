import logging

from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError

from app.services.site_service import MarketplaceManager

logger = logging.getLogger(__name__)

site_routes = Blueprint("site_routes", __name__)


@site_routes.route("/sites", methods=["GET"])
def get_site_list():
    sites = MarketplaceManager.get_all_sites()
    return jsonify([site.to_dict() for site in sites])


@site_routes.route("/sites", methods=["POST"])
def add_site():
    try:
        data = request.json
        new_site = MarketplaceManager.add_site(data)
        return jsonify(new_site.to_dict()), 201
    except Exception as e:
        logger.error(f"Error adding site: {str(e)}")
        return jsonify({"error": "Failed to add site"}), 500


@site_routes.route("/sites/<int:site_id>", methods=["PUT"])
def update_site(site_id):
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400

        # Fetch the current site data
        current_site = MarketplaceManager.get_site(site_id)

        # Determine which fields have changed
        changed_fields = {
            k: v for k, v in data.items() if getattr(current_site, k, None) != v
        }

        if not changed_fields:
            return jsonify({"message": "No changes detected"}), 200

        # Update only the changed fields
        updated_site = MarketplaceManager.update_site(site_id, changed_fields)
        return (
            jsonify(
                {
                    "message": "Site updated successfully",
                    "updated_fields": list(changed_fields.keys()),
                    "site": updated_site.to_dict(),
                }
            ),
            200,
        )

    except ValueError as ve:
        logger.warning(f"Validation error updating site {site_id}: {str(ve)}")
        return jsonify({"error": str(ve)}), 400
    except IntegrityError as ie:
        logger.error(f"Integrity error updating site {site_id}: {str(ie)}")
        return jsonify({"error": "Database integrity error"}), 409
    except Exception as e:
        logger.error(f"Unexpected error updating site {site_id}: {str(e)}")
        return jsonify({"error": "An unexpected error occurred"}), 500
