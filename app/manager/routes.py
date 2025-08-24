from flask import render_template, request, redirect, url_for, flash, session, current_app, jsonify
from flask_login import login_user
from werkzeug.security import check_password_hash
import os
import httpx
import time
from datetime import timedelta
from app.auth.routes import create_jwt

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
                # Set Flask session for manager/admin use
                try:
                    session.permanent = True
                    # Set 20 minutes session lifetime
                    current_app.permanent_session_lifetime = timedelta(minutes=20)
                    session['last_activity'] = int(time.time())
                    session['email'] = manager["email"]
                    session['role'] = manager.get('role', 'manager')
                    session['user_id'] = manager["id"]
                    session['name'] = manager.get('username', manager["email"])            
                except Exception as _e:
                    pass
                # Issue short-lived JWT (5 min default)
                token = create_jwt(manager["email"], session.get('role','manager'))
                flash("Login successful!", "success")
                # If request expects JSON (AJAX), return token & redirect hint
                if request.headers.get('Accept','').find('application/json') >= 0:
                    return jsonify({'status':'success','role':'manager','token':token,'redirect': url_for('admin.dashboard')}), 200
                # Otherwise standard redirect to Admin dashboard
                return redirect(url_for("admin.dashboard"))
            else:
                flash("Invalid password.", "danger")
        else:
            flash("Manager not found.", "danger")
    return render_template("manager_login.html")

# TODO: Implement secure login logic for manager here.
# Signup/registration is handled via Flask CLI only.
# Signup/registration is handled via Flask CLI only.
