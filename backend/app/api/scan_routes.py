from flask import Blueprint, jsonify, request
from app.services.scan_service import PriceScanManager
import logging

logger = logging.getLogger(__name__)

scan_routes = Blueprint('scan_routes', __name__)

@scan_routes.route('/scans', methods=['GET']) 
def get_scans():
    scans = PriceScanManager.get_all_scan_results()
    return jsonify([scan.to_dict() for scan in scans])