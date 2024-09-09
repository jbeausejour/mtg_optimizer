from flask import Blueprint, jsonify
from app.tasks.optimization_tasks import test_task
import logging

logger = logging.getLogger(__name__)

optimization_routes = Blueprint('optimization_routes', __name__)

@optimization_routes.route('/optimize', methods=['POST'])
def start_task():
    logger.info("start-task called")
    task = test_task.apply_async()
    return jsonify({"message": "Task started!", "task_id": task.id})

@optimization_routes.route('/task_status/<task_id>', methods=['GET'])
def task_status(task_id):
    task = test_task.AsyncResult(task_id)
    response = {
        'state': task.state,
        'status': task.info if task.info else ''
    }
    return jsonify(response)