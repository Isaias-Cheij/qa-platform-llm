import os

from flask import Flask, render_template

from qa_platform.config import Config, config


def create_app(config_name=None):
    """Application Factory para crear y configurar la instancia de Flask."""
    if config_name is None:
        config_name = os.getenv("APP_ENV", "development")

    app = Flask(__name__)

    # Cargar configuración desde clase o string de entorno
    if isinstance(config_name, str):
        config_class = config.get(config_name, Config)
    else:
        config_class = config_name

    app.config.from_object(config_class)

    # Ruta inicial: renderiza la vista de bienvenida con la plantilla base
    @app.route("/")
    def index():
        return render_template("index.html")

    return app
