from flask import Flask

from config import Config
from app.routes import api_bp


def create_app(config_class=Config):
    """Application factory for scalable Flask app initialization."""
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config.from_object(config_class)

    app.register_blueprint(api_bp, url_prefix="/api")

    @app.get("/")
    def health_check():
        return {"status": "ok", "service": "MediGuide AI"}, 200

    return app
