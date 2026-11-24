"""Instancias de extensiones de Flask desacopladas de la aplicación.

Este módulo centraliza la creación de extensiones para evitar importaciones
circulares. Cada extensión se instancia sin asociarla a ninguna app concreta;
la vinculación real ocurre dentro de ``create_app()`` mediante el patrón
init_app.
"""

from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

# Instancia global desacoplada. Se inicializa con db.init_app(app) en create_app().
db = SQLAlchemy()
migrate = Migrate()
