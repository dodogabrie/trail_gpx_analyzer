import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from flask_cors import CORS
from config import Config
from database import db, init_db

def create_app(config_class=Config):
    """Application factory."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    app = Flask(__name__, instance_path=os.path.join(base_dir, "instance"))
    app.config.from_object(config_class)

    # Initialize extensions
    CORS(app, supports_credentials=True, origins=app.config['CORS_ORIGINS'])
    init_db(app)

    # Initialize Flask-Migrate
    try:
        from flask_migrate import Migrate
        migrate = Migrate(app, db, directory=os.path.join(base_dir, "migrations"))
    except ImportError:
        pass  # Flask-Migrate not installed, migrations unavailable

    # Register blueprints
    from api import auth, gpx, strava, analysis, prediction, performance
    app.register_blueprint(auth.bp)
    app.register_blueprint(gpx.bp)
    app.register_blueprint(strava.bp)
    app.register_blueprint(analysis.bp)
    app.register_blueprint(prediction.bp)
    app.register_blueprint(performance.bp)

    @app.route('/api/health')
    def health():
        return {'status': 'ok'}

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5000)
