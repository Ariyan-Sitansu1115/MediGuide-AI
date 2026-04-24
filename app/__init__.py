from flask import Flask

from config import Config
from app.routes import api_bp


def create_app(config_class=Config):
    """Application factory for scalable Flask app initialization."""
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config.from_object(config_class)

    # Initialise the SQLite database on first start
    from app.database import init_db

    with app.app_context():
        init_db()

    app.register_blueprint(api_bp, url_prefix="/api")

    @app.get("/")
    def index():
        from flask import render_template

        return render_template("index.html")

    return app
