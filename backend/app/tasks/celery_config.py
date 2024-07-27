import os

class CeleryConfig:
    # Get the absolute path to the project root
    PROJECT_ROOT = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
    
    # Define the instance path
    INSTANCE_PATH = os.path.join(PROJECT_ROOT, 'backend', 'instance')

    broker_connection_retry = True
    broker_connection_max_retries = 5
    broker_connection_retry_on_startup = True

    # Celery Configuration using SQLite
    broker_url = f"sqla+sqlite:///{os.path.join(INSTANCE_PATH, 'celery-broker.sqlite')}"
    result_backend = f"db+sqlite:///{os.path.join(INSTANCE_PATH, 'celery-results.sqlite')}"
    imports = ['app.tasks.optimization_tasks']

    @classmethod
    def init_app(cls, app):
        # Ensure the instance directory exists
        os.makedirs(cls.INSTANCE_PATH, exist_ok=True)

        app.logger.info(f"Celery Broker URL: {cls.broker_url}")
        app.logger.info(f"Celery Result Backend: {cls.result_backend}")
        app.logger.info(f"Instance Path: {cls.INSTANCE_PATH}")

        # Ensure the SQLite files are created and have proper permissions
        for db_file in ['celery-broker.sqlite', 'celery-results.sqlite']:
            db_path = os.path.join(cls.INSTANCE_PATH, db_file)
            if not os.path.exists(db_path):
                open(db_path, 'a').close()  # Create the file if it doesn't exist
            os.chmod(db_path, 0o666)  # Set read and write permissions for everyone

