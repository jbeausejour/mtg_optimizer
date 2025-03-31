import os
import json
import logging
import requests
from flask import Blueprint, current_app, request, jsonify, render_template, make_response, session
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

# Browser service configuration
BROWSER_SERVICE_URL = os.environ.get("BROWSER_SERVICE_URL", "http://mtg-browser-service:3001")

# Create Blueprint for headless cart routes
headless_cart_routes = Blueprint("headless_cart_routes", __name__)


@headless_cart_routes.route("/crystal_commerce/add_to_cart", methods=["POST"])
def add_to_crystal_commerce_cart():
    """Add items to a Crystal Commerce cart using headless browser service"""
    try:
        logger.info("/crystal_commerce/add_to_cart hit")
        data = request.json
        store_url = data.get("store_url")
        cards = data.get("cards", [])
        logger.info(f"Incoming data: {json.dumps(data, indent=2)}")

        if not store_url:
            logger.error("Missing store_url in request")
            return jsonify({"success": False, "error": "Missing store URL"}), 400

        logger.info(f"Processing Crystal Commerce cart for: {store_url}")
        logger.info(f"Adding {len(cards)} cards to cart")

        # Format data for browser service
        payload = {"store_url": store_url, "cards": cards}

        logger.info(f"Sending payload to browser service: {payload}")
        # Call browser service to create session and add items
        response = requests.post(
            urljoin(BROWSER_SERVICE_URL, "/sessions"), json=payload, timeout=120  # Longer timeout for cart operations
        )
        logger.info(f"Browser service responded with status {response.status_code}")

        if response.status_code != 200:
            logger.error(f"Browser service error: {response.status_code} - {response.text}")
            return (
                jsonify({"success": False, "error": "Failed to add items to cart", "details": response.text}),
                response.status_code,
            )

        # Get browser service response
        result = response.json()
        if "text/html" in response.headers.get("Content-Type", ""):
            logger.error(f"Browser service returned HTML: {response.text[:200]}...")
            return jsonify({"success": False, "error": "Unexpected HTML from browser service"}), 502
        # Create response with session details
        return jsonify(
            {
                "success": True,
                "message": f"Added {result['added_count']} of {result['total_cards']} items to cart",
                "session_id": result["session_id"],
                "cart_url": result["cart_url"],
                "proxy_url": result["proxy_url"],
                "added_count": result["added_count"],
                "total_cards": result["total_cards"],
                "errors": result.get("errors"),
            }
        )

    except Exception as e:
        logger.exception(f"Error adding to Crystal Commerce cart: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@headless_cart_routes.route("/proxy_cart", methods=["GET"])
def proxy_cart():
    """Proxy the cart page from the headless browser"""
    try:
        session_id = request.args.get("session_id")

        if not session_id:
            return jsonify({"error": "Missing session_id parameter"}), 400

        # Get session details from browser service
        session_response = requests.get(urljoin(BROWSER_SERVICE_URL, f"/sessions/{session_id}"), timeout=10)

        if session_response.status_code != 200:
            return jsonify({"error": "Session not found or expired"}), 404

        # Get the cart HTML content from browser service
        cart_response = requests.get(urljoin(BROWSER_SERVICE_URL, f"/sessions/{session_id}/cart"), timeout=30)

        # Check if successful
        if cart_response.status_code != 200:
            logger.error(f"Error getting cart content: {cart_response.status_code} - {cart_response.text}")
            return jsonify({"error": "Failed to retrieve cart content"}), 500

        # Return the HTML content
        response = make_response(cart_response.text)
        response.headers["Content-Type"] = "text/html"

        return response

    except Exception as e:
        logger.exception(f"Error proxying cart: {str(e)}")
        return jsonify({"error": "Failed to proxy cart", "details": str(e)}), 500


@headless_cart_routes.route("/redirect_to_cart", methods=["GET"])
def redirect_to_cart():
    session_id = request.args.get("session_id")
    if not session_id:
        return jsonify({"error": "Missing session_id parameter"}), 400

    # Build the URL to the browser service redirect endpoint
    redirect_endpoint = urljoin(
        current_app.config.get("BROWSER_SERVICE_URL", "http://mtg-browser-service:3001"),
        f"/sessions/{session_id}/redirect",
    )
    try:
        browser_response = requests.get(redirect_endpoint, timeout=10)
    except Exception as e:
        current_app.logger.exception("Error calling browser service redirect endpoint")
        return jsonify({"error": "Failed to retrieve redirect page", "details": str(e)}), 500

    # Relay the response from the browser service
    flask_response = make_response(browser_response.text, browser_response.status_code)
    # Forward important headers such as Set-Cookie and Content-Type
    for header in ["set-cookie", "content-type"]:
        if header in browser_response.headers:
            flask_response.headers[header] = browser_response.headers[header]
    return flask_response


@headless_cart_routes.route("/cart_frame", methods=["GET"])
def cart_frame():
    """Renders a page with an iframe containing the proxied cart"""
    try:
        session_id = request.args.get("session_id")

        if not session_id:
            return jsonify({"error": "Missing session_id parameter"}), 400

        # Get session details
        session_response = requests.get(urljoin(BROWSER_SERVICE_URL, f"/sessions/{session_id}"), timeout=10)

        if session_response.status_code != 200:
            return jsonify({"error": "Session not found or expired"}), 404

        session_data = session_response.json()

        # Render a template with iframe
        proxy_url = f"/api/v1/proxy_cart?session_id={session_id}"
        redirect_url = f"/api/v1/redirect_to_cart?session_id={session_id}"

        return render_template(
            "cart_frame.html",
            session_id=session_id,
            proxy_url=proxy_url,
            redirect_url=redirect_url,
            store_url=session_data["store_url"],
            added_count=session_data["added_count"],
            total_cards=session_data["total_cards"],
        )

    except Exception as e:
        logger.exception(f"Error rendering cart frame: {str(e)}")
        return jsonify({"error": "Failed to render cart frame", "details": str(e)}), 500


@headless_cart_routes.route("/cart_preview")
def show_cart_preview():
    session_id = request.args.get("session_id")
    # load session data from Redis here...

    return render_template(
        "cart_frame.html",
        session_id=session_id,
        added_count=session["addedCount"],
        total_cards=session["totalCards"],
        store_url=session["store_url"],
        proxy_url=f"/api/proxy_cart?session_id={session_id}",
        redirect_url=f"{session['store_url']}/checkout/cart",
    )


@headless_cart_routes.route("/release_session", methods=["POST"])
def release_session():
    """Release a browser session"""
    try:
        data = request.json
        session_id = data.get("session_id")

        if not session_id:
            return jsonify({"error": "Missing session_id parameter"}), 400

        # Call browser service to release session
        release_response = requests.delete(urljoin(BROWSER_SERVICE_URL, f"/sessions/{session_id}"), timeout=10)

        if release_response.status_code != 200:
            logger.error(f"Error releasing session: {release_response.status_code} - {release_response.text}")
            return jsonify({"error": "Failed to release session"}), 500

        return jsonify({"success": True, "message": "Session released successfully"})

    except Exception as e:
        logger.exception(f"Error releasing session: {str(e)}")
        return jsonify({"error": "Failed to release session", "details": str(e)}), 500
