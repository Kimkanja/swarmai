"""
Application configuration.

Values are read from environment variables (see .env.example). Never
hard-code secrets here — this file only defines *how* config is loaded,
not the values themselves.
"""

import os
from datetime import timedelta

basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///" + os.path.join(basedir, "instance", "swarmai.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Site-wide settings, used in templates via context processor.
    SITE_NAME = os.environ.get("SITE_NAME", "Swarm AI")
    SITE_DOMAIN = os.environ.get("SITE_DOMAIN", "example.com")
    SUPPORT_EMAIL = os.environ.get("SUPPORT_EMAIL", "support@example.com")
    # Default Telegram contact for manual purchases/support (e.g. https://t.me/your_admin_handle).
    # Individual products can override this via Product.telegram_url.
    SUPPORT_TELEGRAM_URL = os.environ.get("SUPPORT_TELEGRAM_URL", "")

    # License API
    LICENSE_HMAC_SECRET = os.environ.get("LICENSE_HMAC_SECRET", "dev-hmac-secret-change-me")
    LICENSE_API_RATE_LIMIT_PER_HOUR = int(os.environ.get("LICENSE_API_RATE_LIMIT_PER_HOUR", 30))

    # Session / cookies
    PERMANENT_SESSION_LIFETIME = timedelta(days=14)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_DURATION = timedelta(days=14)

    # Uploads
    UPLOAD_FOLDER = os.path.join(basedir, "app", "static", "uploads")
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB

    # Mail (optional)
    MAIL_SERVER = os.environ.get("MAIL_SERVER")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER")

    WTF_CSRF_ENABLED = True


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SESSION_COOKIE_SECURE = False


class ProductionConfig(BaseConfig):
    DEBUG = False
    SESSION_COOKIE_SECURE = True


class TestingConfig(BaseConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}


def get_config():
    env = os.environ.get("FLASK_ENV", "development")
    return config_by_name.get(env, DevelopmentConfig)
