from flask import render_template, redirect, url_for, request, flash, jsonify
from . import admin_bp
from app.auth.routes import supabase

@admin_bp.route('/')
def index():
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/dashboard')
def dashboard():
    return render_template('admin/dashboard.html')

@admin_bp.route('/account-requests')
def admin_account_requests():
    # Add your existing code for account requests here
    return render_template('admin/account_requests.html')
