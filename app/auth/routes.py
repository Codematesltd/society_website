from . import auth_bp
from flask import request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash
import os
import uuid
import re
import smtplib
from email.mime.text import MIMEText
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def send_otp_email(email, otp):
    EMAIL_USER = os.getenv("EMAIL_USER")
    EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
    msg = MIMEText(f"Your OTP for login is: {otp}")
    msg['Subject'] = "Login OTP"
    msg['From'] = EMAIL_USER
    msg['To'] = email
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.send_message(msg)

def send_reset_email(email, token):
    EMAIL_USER = os.getenv("EMAIL_USER")
    EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
    reset_link = f"http://127.0.0.1:5000/auth/reset_password?token={token}"
    msg = MIMEText(f"Click the following link to reset your password:\n{reset_link}")
    msg['Subject'] = "Password Reset Link"
    msg['From'] = EMAIL_USER
    msg['To'] = email
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.send_message(msg)

def find_role(email):
    staff = supabase.table("staff").select("id,email").eq("email", email).execute()
    if staff.data and len(staff.data) > 0:
        return "staff"
    members = supabase.table("members").select("id,email,status").eq("email", email).execute()
    if members.data and len(members.data) > 0:
        return "members"
    return None

@auth_bp.route('/login', methods=['POST'])
def login():
    email = request.form.get('email')
    password = request.form.get('password')
    if not email or not password:
        return jsonify({'status': 'error', 'message': 'Email and password required'}), 400
    role = find_role(email)
    if not role:
        return jsonify({'status': 'error', 'message': 'Email not found'}), 404

    # Check if blocked
    user_row = supabase.table(role).select("id,email,password,login_attempts,blocked").eq("email", email).execute()
    if not user_row.data or not user_row.data[0]:
        return jsonify({'status': 'error', 'message': 'User not found'}), 404
    user = user_row.data[0]
    if user.get("blocked"):
        return jsonify({'status': 'error', 'message': 'Account is blocked'}), 403

    # Check member status if role is members
    if role == "members":
        user_status = supabase.table("members").select("status").eq("email", email).execute()
        if not user_status.data or user_status.data[0].get("status") != "approved":
            return jsonify({'status': 'error', 'message': 'Account not approved by manager'}), 403

    if not user.get("password"):
        return jsonify({'status': 'error', 'message': 'Password not set. Use first-time sign-in.'}), 403

    if not check_password_hash(user['password'], password):
        # Increment login_attempts
        attempts = user.get("login_attempts", 0) + 1
        blocked = attempts >= 3
        supabase.table(role).update({"login_attempts": attempts, "blocked": blocked}).eq("email", email).execute()
        if blocked:
            return jsonify({'status': 'error', 'message': 'Account blocked due to 3 failed attempts'}), 403
        return jsonify({'status': 'error', 'message': f'Invalid password. {3 - attempts} attempts left'}), 401

    # On successful login, always reset login_attempts to zero
    supabase.table(role).update({"login_attempts": 0}).eq("email", email).execute()
    # Redirect according to role (for API, just return role)
    return jsonify({'status': 'success', 'role': role, 'id': user['id']}), 200

@auth_bp.route('/first-time-signin', methods=['POST'])
def first_time_signin():
    email = request.form.get('email')
    if not email or not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return jsonify({'status': 'error', 'message': 'Invalid email'}), 400
    role = find_role(email)
    if not role:
        return jsonify({'status': 'error', 'message': 'Email not found'}), 404
    # Check member status if role is members
    if role == "members":
        user_status = supabase.table("members").select("status").eq("email", email).execute()
        if not user_status.data or user_status.data[0].get("status") != "approved":
            return jsonify({'status': 'error', 'message': 'Account not approved by manager'}), 403
    otp = str(uuid.uuid4().int)[-6:]
    # Store OTP in table
    supabase.table(role).update({"otp": otp}).eq("email", email).execute()
    send_otp_email(email, otp)
    session['otp_email'] = email
    session['otp_role'] = role
    return jsonify({'status': 'success', 'message': 'OTP sent', 'next': 'otp_verification'}), 200

@auth_bp.route('/otp_verification', methods=['POST'])
def otp_verification():
    email = session.get('otp_email')
    role = session.get('otp_role')
    otp = request.form.get('otp')
    if not email or not role or not otp:
        return jsonify({'status': 'error', 'message': 'Session expired or missing data'}), 400
    user = supabase.table(role).select("otp").eq("email", email).execute()
    if not user.data or user.data[0].get("otp") != otp:
        return jsonify({'status': 'error', 'message': 'Invalid OTP'}), 401
    # Clear OTP after use
    supabase.table(role).update({"otp": None}).eq("email", email).execute()
    session['otp_verified'] = True
    return jsonify({'status': 'success', 'next': 'set_password'}), 200

def valid_password(pw):
    if not pw:
        return False
    return (len(pw) >= 8 and
            re.search(r'[A-Za-z]', pw) and
            re.search(r'\d', pw) and
            re.search(r'[^A-Za-z0-9]', pw))

@auth_bp.route('/set_password', methods=['POST'])
def set_password():
    email = session.get('otp_email')
    role = session.get('otp_role')
    otp_verified = session.get('otp_verified')
    password = request.form.get('password')
    if not email or not role or not otp_verified:
        return jsonify({'status': 'error', 'message': 'Session expired or not verified'}), 400
    if not valid_password(password):
        return jsonify({'status': 'error', 'message': 'Password must be at least 8 chars, include letters, numbers, and special chars'}), 400
    hashed = generate_password_hash(password)
    supabase.table(role).update({"password": hashed}).eq("email", email).execute()
    # Clear session
    session.pop('otp_email', None)
    session.pop('otp_role', None)
    session.pop('otp_verified', None)
    return jsonify({'status': 'success', 'message': 'Password set. You can now login.'}), 200

@auth_bp.route('/forgot_password', methods=['POST'])
def forgot_password():
    email = request.form.get('email')
    role = find_role(email)
    if not email or not role:
        return jsonify({'status': 'error', 'message': 'Email not found'}), 404
    # Generate a simple token (for demo, use uuid)
    token = str(uuid.uuid4())
    # Store token in table
    supabase.table(role).update({"reset_token": token}).eq("email", email).execute()
    send_reset_email(email, token)
    return jsonify({'status': 'success', 'message': 'Password reset link sent to email'}), 200

@auth_bp.route('/reset_password', methods=['POST'])
def reset_password():
    token = request.args.get('token') or request.form.get('token')
    password = request.form.get('password')
    # Find user by token in both tables
    for role in ["staff", "members"]:
        user = supabase.table(role).select("email").eq("reset_token", token).execute()
        if user.data and len(user.data) > 0:
            email = user.data[0]["email"]
            if not valid_password(password):
                return jsonify({'status': 'error', 'message': 'Password must be at least 8 chars, include letters, numbers, and special chars'}), 400
            hashed = generate_password_hash(password)
            supabase.table(role).update({"password": hashed, "reset_token": None}).eq("email", email).execute()
            return jsonify({'status': 'success', 'message': 'Password reset successful'}), 200
    return jsonify({'status': 'error', 'message': 'Invalid or expired token'}), 400


