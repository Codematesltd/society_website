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

def find_role(email):
    staff = supabase.table("staff").select("id,email").eq("email", email).execute()
    if staff.data and len(staff.data) > 0:
        return "staff"
    members = supabase.table("members").select("id,email").eq("email", email).execute()
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
    user = supabase.table(role).select("id,email,password").eq("email", email).execute()
    if not user.data or not user.data[0].get("password"):
        return jsonify({'status': 'error', 'message': 'Password not set. Use first-time sign-in.'}), 403
    if not check_password_hash(user.data[0]['password'], password):
        return jsonify({'status': 'error', 'message': 'Invalid password'}), 401
    # Redirect according to role (for API, just return role)
    return jsonify({'status': 'success', 'role': role, 'id': user.data[0]['id']}), 200

@auth_bp.route('/first-time-signin', methods=['POST'])
def first_time_signin():
    email = request.form.get('email')
    if not email or not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return jsonify({'status': 'error', 'message': 'Invalid email'}), 400
    role = find_role(email)
    if not role:
        return jsonify({'status': 'error', 'message': 'Email not found'}), 404
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


