from flask import jsonify
from app import create_app
from dotenv import load_dotenv
import os

load_dotenv()  # Load environment variables

app = create_app()

if __name__ == "__main__":
    # When running directly, use environment variables or defaults
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    host = os.environ.get("FLASK_RUN_HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 5000))

    print(f"Running from main with: host={host}, port={port}, debug={debug}", flush=True)
    app.run(
        debug=debug,
        use_reloader=debug,
        host=host,
        port=port,
    )


@app.route("/api/v1/test-cors", methods=["GET", "OPTIONS"])
def test_cors():
    return jsonify({"message": "CORS is working!"})
