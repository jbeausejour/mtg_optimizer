from dotenv import load_dotenv

from app import create_app

load_dotenv()  # Load environment variables

app = create_app()

if __name__ == "__main__":
    print("Running from main", flush=True)
    app.run(
        debug=app.config["DEBUG"],
        use_reloader=app.config["DEBUG"],
        host="0.0.0.0",
        port=int(app.config.get("PORT", 5000)),
    )
