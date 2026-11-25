import os

from flask import Flask, render_template

from qa_platform.config import Config, config
from qa_platform.extensions import db, migrate


def create_app(config_name=None):
    """Application Factory para crear y configurar la instancia de Flask.

    Args:
        config_name: Nombre del entorno (``'development'``, ``'testing'``,
            ``'production'``) o una clase de configuracion directamente.
            Si es ``None`` se lee la variable de entorno ``APP_ENV``; si
            tampoco existe se usa ``'development'``.

    Returns:
        Instancia de ``flask.Flask`` completamente configurada e inicializada.
    """
    if config_name is None:
        config_name = os.getenv("APP_ENV", "development")

    app = Flask(__name__)

    # Cargar configuracion desde clase o string de entorno
    if isinstance(config_name, str):
        config_class = config.get(config_name, Config)
    else:
        config_class = config_name

    app.config.from_object(config_class)

    # Vincular extensiones a esta instancia concreta de la app.
    # Se hace aqui (y no al instanciar) para respetar el patron Application
    # Factory y evitar importaciones circulares entre modelos y la app.
    db.init_app(app)
    migrate.init_app(app, db)
    from qa_platform import models  # noqa: F401
    from qa_platform.api.health import health_bp
    from qa_platform.api.questions import api_questions_bp
    from qa_platform.web.answers import answers_bp
    from qa_platform.web.auth import auth_bp
    from qa_platform.web.questions import questions_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(api_questions_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(questions_bp)
    app.register_blueprint(answers_bp)

    # Ruta inicial: renderiza la vista de bienvenida con la plantilla base
    @app.route("/")
    def index():
        return render_template("index.html")

    return app
