from flask import Blueprint

# Create blueprint with explicit name parameter
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Do NOT import routes here to avoid circular imports
# We'll register them in a function instead