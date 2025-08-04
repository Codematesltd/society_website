from flask import render_template, request, redirect, url_for, flash
from flask_login import login_user
from werkzeug.security import check_password_hash
import os
import httpx

from . import manager_bp
from .user import AdminUser  # Reuse AdminUser for manager session

@manager_bp.route("/dashboard")
def dashboard():
    return "<h1>Manager Dashboard</h1>"

@manager_bp.route("/login", methods=["GET", "POST"])
def manager_login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_key = os.environ.get("SUPABASE_KEY")
        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
        }
        # Fetch manager by email
        response = httpx.get(
            f"{supabase_url}/rest/v1/manager?email=eq.{email}",
            headers=headers
        )
        if response.status_code == 200 and response.json():
            manager = response.json()[0]
            if check_password_hash(manager["password_hash"], password):
                user = AdminUser(manager["id"], manager["email"])
                login_user(user)
                flash("Login successful!", "success")
                return redirect(url_for("manager.dashboard"))
            else:
                flash("Invalid password.", "danger")
        else:
            flash("Manager not found.", "danger")
    return render_template("manager_login.html")

# TODO: Implement secure login logic for manager here.
# Signup/registration is handled via Flask CLI only.
# Signup/registration is handled via Flask CLI only.
