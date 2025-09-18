import os
from flask import Blueprint

# This blueprint is deprecated, use app/manager/routes.py instead
manager_bp = Blueprint(
    'manager_deprecated',
    __name__,
    url_prefix='/manager_old'
)