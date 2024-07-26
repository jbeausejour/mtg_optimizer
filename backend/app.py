from app import create_app

app = create_app()

if __name__ == "__main__":
    print("Running from main", flush=True)
    with app.app_context():
        app.run(debug=True, use_reloader=True, host='0.0.0.0', port=5000)