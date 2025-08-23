from . import auth_bp
from flask import request, jsonify, session, render_template, redirect, url_for
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

def send_set_password_email(email, token):
    EMAIL_USER = os.getenv("EMAIL_USER")
    EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
    set_link = f"http://127.0.0.1:5000/auth/set_password?token={token}"
    msg = MIMEText(f"Click the following link to set your password:\n{set_link}")
    msg['Subject'] = "Set Your Password"
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

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
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
    
    # Set session variables for staff identity (add these lines)
    try:
        session['email'] = email
        # Get name from user data if available
        user_details = supabase.table(role).select("name,email").eq("email", email).execute()
        if user_details.data and len(user_details.data) > 0:
            session['name'] = user_details.data[0].get('name', email)
            if role == 'staff':
                session['staff_name'] = user_details.data[0].get('name', email)
        # Save the role in session
        session['role'] = role
        session['user_id'] = user['id']
    except Exception as e:
        print(f"Failed to set session variables: {e}")
    
    # Redirect according to role (for API, just return role)
    return jsonify({'status': 'success', 'role': role, 'id': user['id']}), 200

@auth_bp.route('/first_time_signin', methods=['GET'])
def first_time_signin_page():
    return render_template('first_time_signin.html')

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
    # Generate token and store in DB
    token = str(uuid.uuid4())
    supabase.table(role).update({"reset_token": token}).eq("email", email).execute()
    send_set_password_email(email, token)
    return jsonify({'status': 'success', 'message': 'Set password link sent to email'}), 200

@auth_bp.route('/set_password', methods=['GET', 'POST'])
def set_password():
    if request.method == 'GET':
        token = request.args.get('token')
        return render_template('set_password.html', token=token)
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
            return jsonify({'status': 'success', 'message': 'Password set. You can now login.'}), 200
    return jsonify({'status': 'error', 'message': 'Invalid or expired token'}), 400

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

@auth_bp.route('/logout', methods=['GET', 'POST'])
def logout():
    """
    Clear session and redirect user to the login page.
    Uses explicit path '/login' per requirement.
    """
    try:
        session.clear()
    except Exception:
        # if session cannot be cleared for some reason, ignore and continue to redirect
        pass
    return redirect('/login')

def valid_password(password):
    """Validate password meets security requirements"""
    # At least 8 chars, containing letters, numbers, and special chars
    if not password or len(password) < 8:
        return False
    if not re.search(r'[A-Za-z]', password):
        return False
    if not re.search(r'[0-9]', password):
        return False
    if not re.search(r'[^A-Za-z0-9]', password):
        return False
    return True

def notify_admin_loan_application(loan_id, customer_id, loan_type, amount):
    """Send notification to admins about new loan application"""
    try:
        # Get all admin/manager emails
        managers = supabase.table("staff").select("email,name").eq("role", "manager").execute()
        if not managers.data:
            print(f"No managers found to notify about loan {loan_id}")
            return False
            
        # Prepare notification email
        EMAIL_USER = os.getenv("EMAIL_USER")
        EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
        
        subject = f"New Loan Application #{loan_id} Requires Approval"
        body = f"""
        A new loan application has been submitted and requires your approval:
        
        Loan ID: {loan_id}
        Customer ID: {customer_id}
        Loan Type: {loan_type}
        Amount: ₹{amount}
        
        Please login to the management portal to review and approve/reject this application.
        """
        
        # Send to all managers
        for manager in managers.data:
            msg = MIMEText(body)
            msg['Subject'] = subject
            msg['From'] = EMAIL_USER
            msg['To'] = manager['email']
            
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(EMAIL_USER, EMAIL_PASSWORD)
                server.send_message(msg)
                
        return True
    except Exception as e:
        print(f"Failed to notify admins about loan {loan_id}: {e}")
        return False



