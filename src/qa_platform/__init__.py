import os
from flask import Flask

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

    # Ruta inicial para validar que el scaffold responde correctamente
    @app.route("/")
    def index():
        return {
            "name": "Plataforma Q&A con LLM",
            "status": "running",
            "environment": config_name if isinstance(config_name, str) else "custom",
        }

    return app
