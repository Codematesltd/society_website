from flask import Blueprint
from flask_login import LoginManager

manager_bp = Blueprint("manager", __name__, url_prefix="/manager")
login_manager = LoginManager()

from . import routes
# Ensure API routes are registered on the same blueprint
from . import api  # noqa: F401

def register_cli(app):
    from .cli import create_manager
    app.cli.add_command(create_manager)

def init_login(app):
    login_manager.init_app(app)
    from .user import AdminUser

    @login_manager.user_loader
    def load_user(user_id):
        # You may want to fetch the admin from Supabase here
        return None  # Implement as needed

# Usage:
# flask create-manager <username> <email> <password>
# Example:
# flask create-manager admin admin@example.com StrongPassword123
