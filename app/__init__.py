import os
from flask import Flask, render_template

from app.config import get_config
from app.extensions import db, migrate, login_manager, csrf


def create_app(config_object=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_object or get_config())

    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # --- extensions -----------------------------------------------------
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    # --- models (must be imported so Flask-Migrate can see them) --------
    from app.models import user, product, license as license_model, referral, order, settings  # noqa: F401

    @login_manager.user_loader
    def load_user(user_id):
        from app.models.user import User
        return User.query.get(int(user_id))

    # --- blueprints -------------------------------------------------------
    from app.routes.main import main_bp
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.products import products_bp
    from app.routes.referral import referral_bp
    from app.routes.admin import admin_bp
    from app.api.license import license_api_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(dashboard_bp, url_prefix="/dashboard")
    app.register_blueprint(products_bp, url_prefix="/products")
    app.register_blueprint(referral_bp, url_prefix="/referrals")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(license_api_bp, url_prefix="/api/license")

    # The license validation API is called by an EA, not a browser —
    # exempt it from CSRF (it has its own key-based auth instead).
    csrf.exempt(license_api_bp)

    # --- context processors ----------------------------------------------
    @app.context_processor
    def inject_site_settings():
        return {
            "SITE_NAME": app.config["SITE_NAME"],
            "SITE_DOMAIN": app.config["SITE_DOMAIN"],
            "SUPPORT_EMAIL": app.config["SUPPORT_EMAIL"],
            "SUPPORT_TELEGRAM_URL": app.config.get("SUPPORT_TELEGRAM_URL", ""),
        }

    # --- error pages -------------------------------------------------------
    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(500)
    def server_error(e):
        return render_template("errors/500.html"), 500

    # --- CLI commands -------------------------------------------------------
    from app.cli import register_cli
    register_cli(app)

    return app
