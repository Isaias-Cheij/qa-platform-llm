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


class DevelopmentConfig(Config):
    """Configuracion para desarrollo local."""

    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", "sqlite:///qa_platform_dev.db"
    )


class TestingConfig(Config):
    """Configuracion para pruebas automatizadas con PyTest."""

    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


class ProductionConfig(Config):
    """Configuración para entorno de producción."""

    DEBUG = False


config = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}

