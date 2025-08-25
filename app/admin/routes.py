from flask import render_template, redirect, url_for, request, flash, jsonify
from . import admin_bp
from app.auth.decorators import login_required, role_required
from app.auth.routes import supabase
from app.manager.api import send_status_email  # added import

@admin_bp.route('/')
def index():
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/dashboard')
@login_required
@role_required('manager','admin')
def dashboard():
    return render_template('admin/dashboard.html')

# NEW: Add Staff page route (used by dashboard iframe)
@admin_bp.route('/add_staff')
def admin_add_staff():
    return render_template('admin/add_staff.html')

# NEW: Staff Expense page route (if referenced elsewhere)
@admin_bp.route('/staff_expense')
def admin_staff_expense():
    return render_template('admin/staff_expense.html')

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

@admin_bp.route('/account_requests/approve/<path:email>', methods=['POST'])
def approve_member(email):
    """Approve member (moved/duplicated here so route is registered)."""
    try:
        resp = supabase.table("members").update({"status": "approved"}).eq("email", email).execute()
        if not resp.data:
            return jsonify({'status': 'error', 'message': 'Member not found'}), 404
        try:
            send_status_email(email, "approved")
        except Exception as e:
            print(f"Approval email failed: {e}")
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@admin_bp.route('/account_requests/reject/<path:email>', methods=['POST'])
def reject_member(email):
    """Reject member (moved/duplicated here so route is registered)."""
    try:
        resp = supabase.table("members").update({"status": "rejected"}).eq("email", email).execute()
        if not resp.data:
            return jsonify({'status': 'error', 'message': 'Member not found'}), 404
        try:
            send_status_email(email, "rejected")
        except Exception as e:
            print(f"Rejection email failed: {e}")
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
