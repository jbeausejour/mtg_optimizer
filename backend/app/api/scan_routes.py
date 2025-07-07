import logging
from quart import Blueprint, request, jsonify

from app.services.scan_service import ScanService


from celery.result import AsyncResult
from app.utils.async_context_manager import flask_session_scope
from quart_jwt_extended import jwt_required, get_jwt_identity

logger = logging.getLogger(__name__)

# Defining Blueprint for Scan Routes
scan_routes = Blueprint("scan_routes", __name__)


############################################################################################################
# Scan Operations
############################################################################################################


@scan_routes.route("/scans/<int:scan_id>", methods=["GET"])
@jwt_required
async def get_scan_by_id(scan_id):
    async with flask_session_scope() as session:
        try:
            scan = await ScanService.get_scan_results_by_scan_id(session, scan_id)
            if not scan:
                return jsonify({"error": "Scan not found"}), 404
            return jsonify(scan.to_dict())
        except Exception as e:
            logger.error(f"Error fetching scan results: {str(e)}")
            return jsonify({"error": "Failed to fetch scan results"}), 500


@scan_routes.route("/scans", methods=["GET"])
@jwt_required
async def get_all_scans():
    """Get all scans with summary data only (optimized for performance)"""
    async with flask_session_scope() as session:
        try:
            # Use the optimized history method instead of loading all data
            limit = int(request.args.get("limit", 100))  # Default to 100, allow override
            scans = await ScanService.get_scans_history(session, limit)
            
            # Transform to match the expected format
            formatted_scans = []
            for scan in scans:
                formatted_scans.append({
                    "id": scan["id"],
                    "created_at": scan["created_at"].isoformat() if scan["created_at"] else None,
                    "cards_scraped": scan.get("cards_required_total", 0),
                    "sites_scraped": scan.get("sites_scraped", 0),
                })
            
            return jsonify(formatted_scans)
        except Exception as e:
            logger.error(f"Error fetching scans: {str(e)}")
            return jsonify({"error": "Failed to fetch scans"}), 500


@scan_routes.route("/scans/history", methods=["GET"])
@jwt_required
async def get_scan_history():
    """Get scan history without optimization results"""
    async with flask_session_scope() as session:
        try:
            limit = int(request.args.get("limit", 10))
            scans = await ScanService.get_scans_history(session, limit)
            return jsonify(scans)
        except Exception as e:
            logger.error(f"[get_scan_history] Error: {str(e)}")
            return jsonify({"error": "Failed to fetch scan history"}), 500


@scan_routes.route("/scans", methods=["DELETE"])
@jwt_required
async def delete_scans():
    """
    Delete one or more scans.

    Expects a JSON payload with:
    - scan_ids: A list of scan IDs to delete
    """
    try:
        data = await request.get_json()
        user_id = get_jwt_identity()
        scan_ids = data.get("scan_ids")

        if not user_id:
            return jsonify({"error": "User authentication required"}), 401
            
        if not scan_ids:
            return jsonify({"error": "scan_ids are required"}), 400

        if not isinstance(scan_ids, list):
            return jsonify({"error": "scan_ids must be a list"}), 400

        logger.info(f"User {user_id} attempting to delete scans: {scan_ids}")

        async with flask_session_scope() as session:
            deleted, errors = await ScanService.delete_scans(session, scan_ids)
            await session.commit()

        if errors:
            logger.warning(f"Errors during scan deletion: {errors}")

        return jsonify({
            "deleted": deleted, 
            "errors": errors,
            "message": f"Successfully deleted {len(deleted)} scan(s)"
        }), 200 if deleted else 400

    except Exception as e:
        logger.exception(f"Error during bulk scan deletion: {e}")
        return jsonify({"error": "Bulk deletion failed", "details": str(e)}), 500


@scan_routes.route("/scans/delete-many", methods=["DELETE"])
@jwt_required
async def delete_multiple_scans():
    """Optimized bulk delete endpoint"""
    try:
        user_id = get_jwt_identity()
        data = await request.get_json()
        scan_ids = data.get("scan_ids", [])

        if not user_id:
            return jsonify({"error": "User authentication required"}), 401

        if not scan_ids:
            return jsonify({"error": "No scan IDs provided"}), 400

        if not isinstance(scan_ids, list):
            return jsonify({"error": "scan_ids must be a list"}), 400

        logger.info(f"User {user_id} attempting to bulk delete {len(scan_ids)} scans")

        async with flask_session_scope() as session:
            deleted_count = await ScanService.delete_scans_by_ids(session, scan_ids)
            await session.commit()

        logger.info(f"Successfully deleted {deleted_count} scans for user {user_id}")

        return jsonify({
            "deleted_count": deleted_count,
            "message": f"Successfully deleted {deleted_count} scan(s)"
        }), 200

    except Exception as e:
        logger.exception(f"Error during bulk scan deletion: {e}")
        return jsonify({"error": "Bulk deletion failed", "details": str(e)}), 500