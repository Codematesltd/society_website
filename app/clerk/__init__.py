from flask import Blueprint

clerk_bp = Blueprint("clerk", __name__, url_prefix="/clerk")

from . import routes
