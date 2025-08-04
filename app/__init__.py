import os
from flask import Flask
from .config import Config

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Register blueprints
    from .auth import auth_bp
    from .members import members_bp
    from .clerk import clerk_bp
    from .manager import manager_bp
    from .admin import admin_bp
    from .finance import finance_bp
    from .notification import notification_bp
    from .core import core_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(members_bp)
    app.register_blueprint(clerk_bp)
    app.register_blueprint(manager_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(finance_bp)
    app.register_blueprint(notification_bp)
    app.register_blueprint(core_bp)

    return app
