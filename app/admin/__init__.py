from flask import Blueprint

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Import route modules before blueprint registration
from .api import admin_api_bp
admin_bp.register_blueprint(admin_api_bp)

# Register dashboard routes (import executes decorators)
from . import dashboard_routes