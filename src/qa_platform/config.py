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

    # Proveedor LLM activo y credenciales por defecto (Twelve-Factor via env).
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "mock")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    LOCAL_LLM_URL = os.getenv("LOCAL_LLM_URL", "http://localhost:11434/api/generate")
    LOCAL_LLM_MODEL = os.getenv("LOCAL_LLM_MODEL", "llama3")


class DevelopmentConfig(Config):
    """Configuracion para desarrollo local."""

    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///qa_platform_dev.db")


class TestingConfig(Config):
    """Configuracion para pruebas automatizadas con PyTest."""

    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    # En pruebas automatizadas garantizamos el proveedor Mock y sin API keys.
    LLM_PROVIDER = "mock"
    GEMINI_API_KEY = None
    OPENAI_API_KEY = None


class ProductionConfig(Config):
    """Configuración para entorno de producción."""

    DEBUG = False


config = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
