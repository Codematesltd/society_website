import sys
sys.dont_write_bytecode = True

import os
from flask import Flask
from .config import Config

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Register blueprints
    from .auth import auth_bp
    from .members import members_bp
    from .staff import staff_bp
    # now just import the API blueprint
    from .manager.api import manager_bp
    from .finance import finance_bp
    from .notification import notification_bp
    from .core import core_bp
    from app.staff.api import staff_api_bp
    from .admin import admin_bp
    from .admin.api import admin_api_bp  # Add this import

    app.register_blueprint(auth_bp)
    app.register_blueprint(members_bp)
    app.register_blueprint(staff_bp)
    app.register_blueprint(manager_bp)
    # Only register finance_bp once:
    app.register_blueprint(finance_bp)
    app.register_blueprint(notification_bp)
    app.register_blueprint(core_bp)
    app.register_blueprint(staff_api_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(admin_api_bp)  # Add this registration

    return app

def list_routes(app):
    """Print all registered routes with their endpoint and methods."""
    import urllib
    output = []
    for rule in app.url_map.iter_rules():
        methods = ','.join(sorted(rule.methods))
        line = urllib.parse.unquote(f"{rule.endpoint:30s} {methods:25s} {rule}")
        output.append(line)
    for line in sorted(output):
        print(line)

# Example usage:
# In your app.py, after creating the app:
# from app import list_routes
# list_routes(app)
# Example usage:
# In your app.py, after creating the app:
# from app import list_routes
# list_routes(app)
