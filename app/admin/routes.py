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
    # Fetch pending member requests from database
    try:
        resp = supabase.table("members").select("id, name, kgid, email, phone, customer_id").eq("status", "pending").execute()
        requests = resp.data if resp.data else []
        print(f"Found {len(requests)} pending requests")  # Debug line
        return render_template('admin/account_requests.html', requests=requests)
    except Exception as e:
        print(f"Error fetching account requests: {e}")
        return render_template('admin/account_requests.html', requests=[])

@admin_bp.route('/account_requests/approve/<email>', methods=['POST'])
def approve_member(email):
    """Approve a pending member account request"""
    try:
        resp = supabase.table("members").update({"status": "approved"}).eq("email", email).execute()
        if resp.data:
            # Send approval email
            try:
                from app.manager.api import send_status_email
                send_status_email(email, "approved")
            except Exception as e:
                print(f"Error sending approval email: {e}")
            flash("Member approved!", "success")
        else:
            flash("Member not found.", "error")
    except Exception as e:
        print(f"Error approving member: {e}")
        flash("Failed to approve member.", "error")
    return redirect(url_for("admin.admin_account_requests"))

@admin_bp.route('/account_requests/reject/<email>', methods=['POST'])
def reject_member(email):
    """Reject a pending member account request"""
    try:
        resp = supabase.table("members").update({"status": "rejected"}).eq("email", email).execute()
        if resp.data:
            # Send rejection email
            try:
                from app.manager.api import send_status_email
                send_status_email(email, "rejected")
            except Exception as e:
                print(f"Error sending rejection email: {e}")
            flash("Member rejected.", "success")
        else:
            flash("Member not found.", "error")
    except Exception as e:
        print(f"Error rejecting member: {e}")
        flash("Failed to reject member.", "error")
    return redirect(url_for("admin.admin_account_requests"))
