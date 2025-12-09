import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from flask_cors import CORS
from config import Config
from database import db, init_db

def create_app(config_class=Config):
    """Application factory."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    CORS(app, supports_credentials=True, origins=app.config['CORS_ORIGINS'])
    init_db(app)

    # Register blueprints
    from api import auth, gpx, strava, analysis, prediction
    app.register_blueprint(auth.bp)
    app.register_blueprint(gpx.bp)
    app.register_blueprint(strava.bp)
    app.register_blueprint(analysis.bp)
    app.register_blueprint(prediction.bp)

    @app.route('/api/health')
    def health():
        return {'status': 'ok'}

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5000)
