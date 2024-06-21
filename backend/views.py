from flask import Blueprint, jsonify
import os

app = Blueprint('views', __name__)

# Define the path to your data directory
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')

@app.route('/get_site_list', methods=['GET'])
def get_site_list():
    file_path = os.path.join(DATA_DIR, 'site_list.txt')
    with open(file_path, 'r') as file:
        content = file.readlines()
    return jsonify(content)

@app.route('/get_buy_list', methods=['GET'])
def get_buy_list():
    file_path = os.path.join(DATA_DIR, 'buy_list.txt')
    with open(file_path, 'r') as file:
        content = file.readlines()
    return jsonify(content)
