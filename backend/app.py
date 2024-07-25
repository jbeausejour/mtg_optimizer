
from app import create_app
from app.tasks.celery_app import make_celery

app = create_app()
celery = make_celery(app)

if __name__ == "__main__":
    #logger.debug("Running from main")
    print("Running from main", flush=True)
    #celery = make_celery(app)
    with app.app_context():
        #logger.debug("Starting Flask app")
        app.run(debug=True, use_reloader=True, host='0.0.0.0', port=5000)