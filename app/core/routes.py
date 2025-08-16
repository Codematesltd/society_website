from . import core_bp
from flask import render_template

@core_bp.route("/")
def home():
    return render_template("landing_page.html")

@core_bp.route("/about")
def about():
    return render_template("about.html")

@core_bp.route("/services")
def services():
    return render_template("services.html")

@core_bp.route("/contact")
def contact():
    return render_template("contact.html")
