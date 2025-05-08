from quart import Quart, jsonify
from app import create_app
import os

app = create_app()

if __name__ == "__main__":
    # When running directly, use environment variables or defaults
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    host = os.environ.get("FLASK_RUN_HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 5000))

    print(f"Running from main with: host={host}, port={port}, debug={debug}", flush=True)
    import uvicorn

    uvicorn.run("app:app", host=host, port=port, reload=debug)


@app.route("/api/v1/test-cors", methods=["GET", "OPTIONS"])
async def test_cors():
    return jsonify({"message": "CORS is working!"})
