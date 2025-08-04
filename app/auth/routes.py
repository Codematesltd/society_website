from . import auth_bp
from flask import render_template, redirect, url_for

@auth_bp.route("/login")
def login():
    return "<h1>Login Page</h1>"
