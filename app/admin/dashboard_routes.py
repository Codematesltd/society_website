from . import admin_bp
from flask import render_template, request, redirect, url_for, flash
import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

@admin_bp.route("/dashboard")
def dashboard():
    # Provide all variables used in the template with default values
    return render_template(
        "admin/dashboard.html",
        total_customers=0,
        active_loans=0,
        total_statement=0
    )

@admin_bp.route("/account_requests/approve/<email>", methods=["POST"])
def approve_member(email):
    # Approve member by email
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

@admin_bp.route("/account_requests/reject/<email>", methods=["POST"])
def reject_member(email):
    # Reject member by email
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

@admin_bp.route("/staff_expense")
def admin_staff_expense():
    return render_template("admin/staff_expense.html")

@admin_bp.route("/add_staff")
def admin_add_staff():
    return render_template("admin/add_staff.html")
@admin_bp.route("/staff_expense")
def admin_staff_expense():
    return render_template("admin/staff_expense.html")

@admin_bp.route("/add_staff")
def admin_add_staff():
    return render_template("admin/add_staff.html")
