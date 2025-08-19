from flask import Blueprint

# Single finance blueprint used by both UI routes and API endpoints.
# Use URL prefix '/loan' so API routes like '/loan/apply' match expectations.
finance_bp = Blueprint("finance", __name__, url_prefix="/loan")

# Import submodules to register their routes on the shared blueprint.
from . import routes, api
from .loan_certificate import register_certificate_routes

# Register certificate routes
register_certificate_routes(finance_bp)
