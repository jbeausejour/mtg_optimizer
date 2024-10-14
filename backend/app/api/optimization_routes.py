import logging

from flask import Blueprint, jsonify, request

from app.tasks.optimization_tasks import start_scraping_task, test_task

logger = logging.getLogger(__name__)

optimization_routes = Blueprint("optimization_routes", __name__)


@optimization_routes.route("/optimize", methods=["POST"])
def start_task():
    logger.info("start-task called")
    task = test_task.apply_async()
    return jsonify({"message": "Task started!", "task_id": task.id})


@optimization_routes.route("/task_status/<task_id>", methods=["GET"])
def task_status(task_id):
    task = test_task.AsyncResult(task_id)
    response = {"state": task.state, "status": task.info if task.info else ""}
    return jsonify(response)


@optimization_routes.route("/start_scraping", methods=["POST"])
def start_scraping():
    data = request.json

    # Extracting parameters from request data
    site_ids = data.get("sites", [])
    card_list = data.get("card_list", [])
    # Default to 'milp' if not provided
    strategy = data.get("strategy", "milp")
    min_store = data.get("min_store", 1)
    find_min_store = data.get("find_min_store", False)

    # Validating required fields
    if not site_ids or not card_list:
        return jsonify({"error": "Missing site_ids or card_list"}), 400

    # Trigger the task using apply_async with all parameters
    task = start_scraping_task.apply_async(
        args=[site_ids, card_list, strategy, min_store, find_min_store]
    )
    return jsonify({"task_id": task.id}), 202
