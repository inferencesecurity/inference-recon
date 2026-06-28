"""Flask app factory."""
# app/__init__.py
from flask import Flask
from app.routes.admin import admin_bp
from app.routes.public import public_bp
from app.auth import login_required_for_blueprint


def create_app():
    app = Flask(__name__)
    app.config.from_object("app.config.Production")

    # Public routes — no auth needed by design.
    app.register_blueprint(public_bp)

    # API routes get auth middleware applied at the blueprint level.
    from app.routes.api import api_bp
    login_required_for_blueprint(api_bp)
    app.register_blueprint(api_bp, url_prefix="/api")


    # Admin routes
    app.register_blueprint(admin_bp, url_prefix="/admin")

    return app
