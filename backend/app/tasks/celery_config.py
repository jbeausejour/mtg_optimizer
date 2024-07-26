import os

basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

class CeleryConfig:

    # Get the absolute path to the project root
    PROJECT_ROOT = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    
    # Define the instance path
    INSTANCE_PATH = os.path.join(PROJECT_ROOT, 'instance')
    
    @classmethod
    def init_app(cls, app):
        # Ensure the SQLite files are created and have proper permissions
        for db_file in ['celery-broker.sqlite', 'celery-results.sqlite']:
            db_path = os.path.join(cls.INSTANCE_PATH, db_file)
            if not os.path.exists(db_path):
                open(db_path, 'a').close()  # Create the file if it doesn't exist
            os.chmod(db_path, 0o666)  # Set read and write permissions for everyone
        
    # Celery Configuration using SQLite
    broker_url = f"sqla+sqlite:///{os.path.join(basedir, 'instance', 'celery-broker.sqlite')}"
    result_backend = f"db+sqlite:///{os.path.join(basedir, 'instance', 'celery-results.sqlite')}"
    imports = ['app.tasks.optimization_tasks']
    broker_connection_retry_on_startup = True
