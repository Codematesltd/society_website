from . import staff_bp
from flask import render_template

@staff_bp.route("/dashboard")
def dashboard():
    return render_template("staff_dashboard.html")
