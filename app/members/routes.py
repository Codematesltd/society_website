from flask import render_template
from . import members_bp

@members_bp.route("/dashboard")
def dashboard():
    return render_template('user_dashboard.html')
