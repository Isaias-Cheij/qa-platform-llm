import os


class Config:
    """Configuracion base comun a todos los entornos."""

    SECRET_KEY = os.getenv("SECRET_KEY", "development-only-secret-key")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///qa_platform.db")
    # Desactivar el sistema de seguimiento de modificaciones de Flask-SQLAlchemy
    # para reducir overhead en memoria. Se recomienda desactivarlo siempre que
    # no se utilicen las senales de Flask-SQLAlchemy explicitamente.
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TESTING = False

    # Configuración opcional para el servicio de respuestas con LLM.
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    LLM_API_KEY = os.getenv("LLM_API_KEY") or GEMINI_API_KEY or OPENAI_API_KEY


class DevelopmentConfig(Config):
    """Configuracion para desarrollo local."""

    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///qa_platform_dev.db")


class TestingConfig(Config):
    """Configuracion para pruebas automatizadas con PyTest."""

    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    # En pruebas automatizadas desactivamos las claves reales por defecto para
    # garantizar el uso del fallback local sin llamadas de red accidentales.
    OPENAI_API_KEY = None
    GEMINI_API_KEY = None
    LLM_API_KEY = None


class ProductionConfig(Config):
    """Configuración para entorno de producción."""

    DEBUG = False


config = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
