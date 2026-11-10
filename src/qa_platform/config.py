import os


class Config:
    """Configuración base común a todos los entornos."""

    SECRET_KEY = os.getenv("SECRET_KEY", "development-only-secret-key")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///qa_platform.db")
    TESTING = False


class DevelopmentConfig(Config):
    """Configuración para desarrollo local."""

    DEBUG = True


class TestingConfig(Config):
    """Configuración para pruebas automatizadas con PyTest."""

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
