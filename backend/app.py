from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS

db = SQLAlchemy()

def create_app():
    app = Flask(__name__, static_folder='static', template_folder='templates')
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sites.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    CORS(app)
    db.init_app(app)

    from views import views
    app.register_blueprint(views)

    with app.app_context():
        db.create_all()

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
