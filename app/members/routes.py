from flask import render_template, request, jsonify, session
from werkzeug.security import check_password_hash
from app.auth.routes import supabase
from . import members_bp

@members_bp.route("/dashboard")
def dashboard():
    return render_template('user_dashboard.html')

@members_bp.route("/api/check-balance", methods=["POST"])
def api_check_balance():
    """
    API to check member balance after verifying password.
    Expects JSON: { "password": "plain_password" }
    Returns: { "status": "success", "balance": amount } or error message.
    """
    user_email = session.get("email")
    if not user_email:
        return jsonify({"status": "error", "message": "Not logged in"}), 401

    data = request.get_json(silent=True) or {}
    password = data.get("password")
    if not password:
        return jsonify({"status": "error", "message": "Password required"}), 400

    # Fetch member by email
    member_resp = supabase.table("members").select("password,balance").eq("email", user_email).execute()
    if not member_resp.data:
        return jsonify({"status": "error", "message": "Member not found"}), 404

    member = member_resp.data[0]
    hashed_pw = member.get("password")
    if not hashed_pw or not check_password_hash(hashed_pw, password):
        return jsonify({"status": "error", "message": "Incorrect password"}), 403

    balance = member.get("balance", 0)
    return jsonify({"status": "success", "balance": balance}), 200
