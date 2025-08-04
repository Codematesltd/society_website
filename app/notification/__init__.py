from flask import Blueprint

notification_bp = Blueprint("notification", __name__, url_prefix="/notification")

from . import routes
