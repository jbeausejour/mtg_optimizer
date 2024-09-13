from flask import Blueprint, jsonify, request
from app.tasks.optimization_tasks import test_task, start_scraping_task
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

@optimization_routes.route('/start_scraping', methods=['POST'])
def start_scraping():
    data = request.json
    site_ids = data.get('site_ids', [])
    card_names = data.get('card_names', [])
    
    if not site_ids or not card_names:
        return jsonify({'error': 'Missing site_ids or card_names'}), 400

    # Trigger the task using apply_async
    task = start_scraping_task.apply_async(args=[site_ids, card_names])
    return jsonify({'task_id': task.id}), 202