import logging
from quart import Blueprint, request, jsonify

from app.services.site_service import SiteService


from celery.result import AsyncResult
from app.utils.async_context_manager import flask_session_scope
from quart_jwt_extended import jwt_required, get_jwt_identity

logger = logging.getLogger(__name__)

# Defining Blueprint for Site Routes
site_routes = Blueprint("site_routes", __name__)


############################################################################################################
# Site Operations
############################################################################################################


@site_routes.route("/sites", methods=["GET"])
@jwt_required
async def get_sites():
    async with flask_session_scope() as session:
        try:
            sites = await SiteService.get_all_sites(session=session)
            return jsonify([site.to_dict() for site in sites])

        except Exception as e:
            logger.exception(f"Error fetching sites: {e}")
            return jsonify({"error": str(e)}), 500


@site_routes.route("/sites", methods=["POST"])
@jwt_required
async def add_site():
    try:
        data = await request.get_json()
        async with flask_session_scope() as session:
            new_site = await SiteService.add_site(session, data)
            await session.commit()
            return jsonify(new_site.to_dict()), 201
    except Exception as e:
        logger.error(f"Error adding site: {str(e)}")
        return jsonify({"error": "Failed to add site"}), 500


@site_routes.route("/sites/<int:site_id>", methods=["PUT"])
@jwt_required
async def update_site(site_id):
    try:
        data = await request.get_json()
        if not data:
            return jsonify({"status": "warning", "message": "No data provided for update"}), 400

        async with flask_session_scope() as session:
            updated_site = await SiteService.update_site(session, site_id, data)
            await session.commit()
            if not updated_site:
                return (
                    jsonify({"status": "info", "message": "No changes were needed - site data is already up to date"}),
                    200,
                )
            return (
                jsonify(
                    {
                        "status": "success",
                        "message": "Site updated successfully",
                        "site": updated_site.to_dict(),
                    }
                ),
                200,
            )

    except ValueError as ve:
        return jsonify({"status": "warning", "message": str(ve)}), 400
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({"status": "error", "message": "An unexpected error occurred while updating the site"}), 500


@site_routes.route("/sites/<int:site_id>", methods=["DELETE"])
@jwt_required
async def delete_site(site_id):
    try:
        async with flask_session_scope() as session:
            deleted = await SiteService.delete_site(session, site_id)
            await session.commit()
            if deleted:
                return jsonify({"status": "success", "message": "Site deleted successfully"}), 200
            else:
                return jsonify({"status": "error", "message": "Site not found"}), 404
    except Exception as e:
        logger.error(f"Error deleting site: {str(e)}")
        return jsonify({"status": "error", "message": "Failed to delete site"}), 500


@site_routes.route("/sites/delete-many", methods=["DELETE"])
@jwt_required
async def delete_multiple_sites():
    user_id = get_jwt_identity()
    data = await request.get_json()
    site_ids = data.get("site_ids", [])

    logger.info(f"User {user_id} requested deletion of {len(site_ids)} sites ")
    async with flask_session_scope() as session:
        deleted_ids = await SiteService.delete_sites_by_ids(session, site_ids)
        await session.commit()

    return jsonify({"deleted_ids": deleted_ids}), 200
