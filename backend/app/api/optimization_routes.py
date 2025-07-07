import logging
import time
from quart import Blueprint, request, jsonify

from app.services.card_service import CardService
from app.services.site_service import SiteService
from app.services.optimization_service import OptimizationService

from celery.result import AsyncResult
from app.tasks.optimization_tasks import celery_app, start_scraping_task
from app.utils.async_context_manager import flask_session_scope
from quart_jwt_extended import jwt_required, get_jwt_identity

logger = logging.getLogger(__name__)

# Defining Blueprint for optimization and tasks Routes
optimization_routes = Blueprint("optimization_routes", __name__)


############################################################################################################
# Task Operations
############################################################################################################


@optimization_routes.route("/task_status/<task_id>")
def get_task_status(task_id):
    """Get task status with better error handling"""
    try:
        result = AsyncResult(task_id)

        # Check if task exists and is valid
        if not result:
            return jsonify({"state": "PENDING", "status": "Task not found", "progress": 0, "error": "Task not found"})

        # Get task state safely
        try:
            state = result.state
        except Exception as e:
            logger.warning(f"Failed to get task state for {task_id}: {e}")
            state = "UNKNOWN"

        # Get task info safely
        task_info = {}
        try:
            # Prefer .info (state metadata), fallback to result
            if hasattr(result, "info") and isinstance(result.info, dict):
                task_info = result.info
            elif isinstance(result.result, dict):
                task_info = result.result
        except Exception as e:
            logger.warning(f"Failed to extract task info for {task_id}: {e}")

        # Handle different states
        if state == "PENDING":
            response = {"state": state, "status": "Task is pending...", "progress": 0}
        elif state == "PROCESSING":
            response = {
                "state": state,
                "status": task_info.get("status", "Processing..."),
                "progress": task_info.get("progress", 0),
                "current": {"subtasks": task_info.get("current", {}).get("subtasks", {})},
                "details": task_info.get("details"),
            }
        elif state == "SUCCESS":
            if task_info:
                response = {
                    "state": state,
                    "status": "Task completed successfully",
                    "progress": 100,
                    "result": task_info,
                }
            else:
                # Try to get the actual result
                try:
                    task_result = result.result
                    response = {
                        "state": state,
                        "status": "Task completed successfully",
                        "progress": 100,
                        "result": task_result,
                    }
                except Exception as e:
                    logger.warning(f"Failed to get task result for {task_id}: {e}")
                    response = {
                        "state": state,
                        "status": "Task completed but result unavailable",
                        "progress": 100,
                        "error": str(e),
                    }
        elif state == "FAILURE":
            # Handle failure state carefully
            error_message = "Task failed"
            if task_info:
                if isinstance(task_info, dict):
                    error_message = task_info.get("error", str(task_info))
                else:
                    error_message = str(task_info)

            response = {"state": state, "status": "Task failed", "progress": 100, "error": error_message}
        else:
            # Unknown or other states
            response = {
                "state": state,
                "status": f"Task in unknown state: {state}",
                "progress": 0,
                "error": f"Unknown task state: {state}",
            }

        return jsonify(response)

    except Exception as e:
        logger.exception(f"Error checking task status for {task_id}: {e}")
        return jsonify({"state": "ERROR", "status": "Failed to check task status", "progress": 0, "error": str(e)}), 500


# Also add this helper function for better task monitoring
def safe_get_task_info(task_id, max_retries=3):
    """Safely get task information with retries"""
    for attempt in range(max_retries):
        try:
            result = AsyncResult(task_id)
            return {
                "state": result.state,
                "info": result.info if hasattr(result, "info") else None,
                "result": result.result if result.state == "SUCCESS" else None,
            }
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1} failed to get task info for {task_id}: {e}")
            if attempt == max_retries - 1:
                return {"state": "ERROR", "info": None, "result": None, "error": str(e)}
            time.sleep(0.1 * (attempt + 1))  # Exponential backoff

    return None


@optimization_routes.route("/cancel_task/<task_id>", methods=["POST"])
@jwt_required
async def cancel_task(task_id):
    main_result = AsyncResult(task_id)

    # Try to find subtasks from state or result
    subtasks = []
    if isinstance(main_result.result, dict) and "subtask_ids" in main_result.result:
        subtasks = main_result.result["subtask_ids"]

    elif isinstance(main_result.info, dict) and "subtask_ids" in main_result.info:
        subtasks = main_result.info["subtask_ids"]

    # Revoke subtasks
    for sid in subtasks:
        celery_app.control.revoke(sid, terminate=True, signal="SIGTERM")

    # Revoke main task
    celery_app.control.revoke(task_id, terminate=True, signal="SIGTERM")

    logger.info(f"Canceled task {task_id} and subtasks {subtasks}")
    return jsonify({"status": "REVOKED", "task_id": task_id, "subtasks": subtasks})


############################################################################################################
# Optimization Operations
############################################################################################################


@optimization_routes.route("/start_scraping", methods=["POST"])
@jwt_required
async def start_scraping():
    """Starts the scraping and optimization task."""
    data = await request.get_json()

    user_id = get_jwt_identity()
    logger.info(f"User {user_id} starting optimization")

    # Extract parameters from request
    buylist_id = int(data.get("buylist_id", 0))
    site_ids = data.get("sites", [])
    card_list_from_frontend = data.get("card_list", [])
    min_age_seconds = data.get("min_age_seconds", 3600)

    # Get optimization configuration
    # Support both old and new parameter styles
    optimization_config = data.get("optimization_config")
    if optimization_config:
        # New style - full config object from frontend
        strategy = optimization_config.get("primary_algorithm", "milp")
        min_store = optimization_config.get("min_store", 1)
        max_store = optimization_config.get("max_store", 10)
        find_min_store = optimization_config.get("find_min_store", False)
        strict_preferences = optimization_config.get("strict_preferences", False)
        weights = optimization_config.get("weights", {})

    # Get user preferences
    user_preferences = data.get("user_preferences", {})

    # Log configuration
    logger.info(f"Optimization configuration:")
    logger.info(f"  buylist_id: {buylist_id}")
    logger.info(f"  strategy: {strategy}")
    logger.info(f"  min_store: {min_store}")
    logger.info(f"  max_store: {max_store}")
    logger.info(f"  find_min_store: {find_min_store}")
    logger.info(f"  strict_preferences: {strict_preferences}")
    logger.info(f"  weights: {weights}")

    # Filter out default preferences to reduce logging noise
    DEFAULT_PREFS = {"set_name": None, "language": "English", "quality": "NM", "version": "Standard"}
    filtered_user_preferences = {card: prefs for card, prefs in user_preferences.items() if prefs != DEFAULT_PREFS}
    if filtered_user_preferences:
        logger.info(f"Non-default user preferences: {filtered_user_preferences}")

    # Validate required parameters
    if not site_ids or not card_list_from_frontend:
        return jsonify({"error": "Missing site_ids or card_list"}), 400

    if not buylist_id:
        return jsonify({"error": "buylist_id is required"}), 400

    # Create complete configuration for the task
    # This merges all parameters into a single config object
    complete_config = {
        "primary_algorithm": strategy,
        "min_store": min_store,
        "max_store": max_store,
        "find_min_store": find_min_store,
        "strict_preferences": strict_preferences,
        "weights": weights,
        "user_preferences": user_preferences,
    }

    # Add algorithm-specific parameters if provided
    if optimization_config:
        algorithm_params = [
            "time_limit",
            "max_iterations",
            "early_stopping",
            "convergence_threshold",
            "population_size",
            "neighborhood_size",
            "decomposition_method",
            "milp_gap_tolerance",
            "hybrid_milp_time_fraction",
        ]
        for param in algorithm_params:
            if param in optimization_config:
                complete_config[param] = optimization_config[param]

    # Add any algorithm config from frontend
    algorithm_config = data.get("algorithm_config", {})
    complete_config.update(algorithm_config)

    # Start the task with all parameters
    task = start_scraping_task.apply_async(
        args=[
            site_ids,
            card_list_from_frontend,
            strategy,  # Keep for backward compatibility
            min_store,
            max_store,
            find_min_store,
            min_age_seconds,
            buylist_id,
            user_id,
            strict_preferences,
            user_preferences,
            weights,
        ],
        kwargs={"complete_config": complete_config},  # Pass complete config as kwarg
    )

    logger.info(f"Started optimization task {task.id}")
    return jsonify({"task_id": task.id}), 202


@optimization_routes.route("/purchase_order", methods=["POST"])
@jwt_required
async def generate_purchase_links():
    try:
        data = await request.get_json()
        purchase_data = data.get("purchase_data", [])

        async with flask_session_scope() as session:
            active_sites = {site.id: site for site in await SiteService.get_all_sites(session)}
            results = await CardService.generate_purchase_links(purchase_data, active_sites)
            # logger.info(f"return data: {results}")
            return jsonify(results), 200

    except Exception as e:
        logger.error(f"Error generating purchase links: {str(e)}")
        return jsonify({"error": "Failed to generate purchase links"}), 500


############################################################################################################
# Results Operations
############################################################################################################


@optimization_routes.route("/results/<int:scan_id>", methods=["GET"])
@jwt_required
async def get_scan_optimization_result(scan_id):
    """Get optimization results for a specific scan"""
    async with flask_session_scope() as session:
        opt_results = await OptimizationService.get_optimization_results_by_scan(session, scan_id)
        if not opt_results or len(opt_results) == 0:
            return jsonify({"error": "No optimization results found"}), 404

        opt_result = opt_results[0]  # Get the first/latest result

        response = {
            "id": scan_id,
            "created_at": opt_result.created_at.isoformat(),
            "solutions": opt_result.solutions,
            "status": opt_result.status,
            "message": opt_result.message,
            "sites_scraped": opt_result.sites_scraped,
            "cards_scraped": opt_result.cards_scraped,
            "errors": opt_result.errors,
        }

        return jsonify(response)


@optimization_routes.route("/results/latest", methods=["GET"])
@jwt_required
async def get_latest_optimization_results():
    async with flask_session_scope() as session:
        opt_result = await OptimizationService.get_latest_optimization(session)
        if not opt_result:
            return jsonify({"error": "No optimization results found"}), 404

        response = {
            "id": opt_result.scan_id,
            "created_at": opt_result.created_at.isoformat(),
            "optimization": opt_result.to_dict(),
        }

        return jsonify(response)


@optimization_routes.route("/results/<int:id>", methods=["DELETE"])
@jwt_required
async def delete_optimization_result(id):
    """Delete optimization result for a specific ID"""
    user_id = get_jwt_identity()
    logger.info(f"User {user_id} requested deletion of optimization result for id: {id}")

    async with flask_session_scope() as session:
        success = await OptimizationService.delete_optimization_by_id(session, id)
        await session.commit()

        if success:
            return jsonify({"message": f"Optimization result for id {id} deleted"}), 200
        else:
            return jsonify({"error": f"No result found for id {id}"}), 404


@optimization_routes.route("/results/bulk-delete", methods=["DELETE"])
@jwt_required
async def delete_bulk_optimization_results():
    """Delete multiple optimization results by ID list"""
    user_id = get_jwt_identity()
    data = await request.get_json()

    ids = data.get("ids", [])
    if not isinstance(ids, list) or not all(isinstance(i, int) for i in ids):
        return jsonify({"error": "ids must be a list of integers"}), 400

    logger.info(f"User {user_id} requested bulk deletion of optimization result for {len(ids)} results")

    try:
        async with flask_session_scope() as session:
            deleted_ids = await OptimizationService.delete_bulk_by_ids(session, ids)
            await session.commit()

        return (
            jsonify(
                {
                    "message": f"{len(deleted_ids)} optimization results deleted",
                    "deleted_ids": deleted_ids,
                    "requested_count": len(ids),
                    "success": True,
                }
            ),
            200,
        )

    except Exception as e:
        logger.error(f"Error in bulk delete operation: {str(e)}")
        return jsonify({"error": "Failed to delete optimization results", "message": str(e), "success": False}), 500


@optimization_routes.route("/results", methods=["GET"])
@jwt_required
async def get_optimization_results():
    """
    Enhanced endpoint to get optimization results with full algorithm and performance data
    Uses the service layer properly with async SQLAlchemy patterns
    """
    try:
        # Get query parameters for filtering and limiting
        limit = request.args.get("limit", None, type=int)
        algorithm_filter = request.args.get("algorithm", None)
        status_filter = request.args.get("status", None)

        # Note: page and per_page parameters are retrieved but not used in the current implementation
        # This is because the frontend is using infinite scroll or simple limits instead of pagination
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 50, type=int)

        logger.info(
            f"Getting optimization results with filters: limit={limit}, algorithm={algorithm_filter}, status={status_filter}"
        )

        async with flask_session_scope() as session:
            # Use the service method with proper async patterns
            enhanced_results = await OptimizationService.get_optimization_results_enhanced(
                session=session, limit=limit, algorithm_filter=algorithm_filter, status_filter=status_filter
            )

            logger.info(f"Found {len(enhanced_results)} optimization results")
            return jsonify(enhanced_results)

    except Exception as e:
        logger.error(f"Error fetching optimization results: {str(e)}")
        return jsonify({"error": "Failed to fetch results"}), 500


@optimization_routes.route("/optimization_analytics", methods=["GET"])
@jwt_required
async def get_optimization_analytics():
    """
    Endpoint to get aggregated performance analytics across all optimizations
    Uses the service layer properly with async SQLAlchemy patterns
    """
    try:
        logger.info("Generating optimization analytics")

        async with flask_session_scope() as session:
            # Use the service method with proper async patterns
            analytics = await OptimizationService.get_optimization_analytics(session=session)

            logger.info(f"Generated analytics for {analytics.get('total_optimizations', 0)} optimizations")
            return jsonify(analytics)

    except Exception as e:
        logger.error(f"Error generating analytics: {str(e)}")
        return jsonify({"error": "Failed to generate analytics"}), 500


@optimization_routes.route("/results_simple", methods=["GET"])
@jwt_required
async def get_optimization_results_simple():
    """
    Simplified endpoint that manually adds the missing fields
    Uses the service layer properly with async SQLAlchemy patterns
    """
    try:
        limit = request.args.get("limit", None, type=int)

        logger.info(f"Getting simple optimization results with limit={limit}")

        async with flask_session_scope() as session:
            # Use the service method with proper async patterns
            results_data = await OptimizationService.get_optimization_results_simple(session=session, limit=limit)

            logger.info(f"Found {len(results_data)} optimization results")
            return jsonify(results_data)

    except Exception as e:
        logger.error(f"Error fetching simple results: {str(e)}")
        return jsonify({"error": "Failed to fetch results"}), 500
