"""Paquete de Blueprints web (vistas HTML con Jinja2)."""

from qa_platform.web.auth import auth_bp, login_required

__all__ = ["auth_bp", "login_required"]
