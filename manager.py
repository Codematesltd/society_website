import os
from flask import Blueprint, render_template

manager_bp = Blueprint(
    'manager',
    __name__,
    url_prefix='/manager',
    template_folder=os.path.join(os.path.dirname(__file__), 'templates')
)

@manager_bp.route('/login')
def manager_login():
    return render_template('manager_login.html')