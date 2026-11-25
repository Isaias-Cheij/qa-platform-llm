"""Blueprints de la API JSON de qa-platform."""

from qa_platform.api.health import health_bp
from qa_platform.api.questions import api_questions_bp

__all__ = ["api_questions_bp", "health_bp"]
