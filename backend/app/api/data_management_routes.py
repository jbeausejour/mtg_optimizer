import asyncio
import logging

from flask import Blueprint, jsonify

from app.utils.data_fetcher import ExternalDataSynchronizer
from app.utils.load_initial_data import load_all_data, truncate_tables

logger = logging.getLogger(__name__)

data_management_routes = Blueprint("data_management_routes", __name__)


@data_management_routes.route("/update_card_data", methods=["POST"])
def update_card_data():
    try:
        asyncio.run(ExternalDataSynchronizer.update_all_cards())
        return (
            jsonify(
                {
                    "status": "success",
                    "message": "Card data update process has been initiated.",
                }
            ),
            202,
        )
    except Exception as e:
        logger.error(f"Error updating card data: {str(e)}")
        return (
            jsonify({"status": "error", "message": f"An error occurred: {str(e)}"}),
            500,
        )


@data_management_routes.route("/load-data", methods=["POST"])
def load_data():
    try:
        logger.info("Starting data truncation")
        truncate_tables()
        logger.info("Data truncation completed")

        logger.info("Starting data loading")
        load_all_data()
        logger.info("Data loading completed successfully")

        return jsonify({"message": "Data loaded successfully"}), 200
    except Exception as e:
        logger.error(f"Error during data loading: {str(e)}")
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500
