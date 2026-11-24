"""Blueprint del endpoint de verificacion de salud del servicio."""

from flask import Blueprint

health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
def health():
    """Verifica que la aplicacion esta activa y respondiendo.

    Returns:
        Tupla con diccionario JSON de estado y codigo HTTP 200.
    """
    return {"status": "ok"}, 200
