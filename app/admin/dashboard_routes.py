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

@admin_bp.route("/account_requests")
def admin_account_requests():
    # Fetch all pending member requests - INCLUDE customer_id
    resp = supabase.table("members").select("id, name, kgid, email, phone, customer_id").eq("status", "pending").execute()
    requests = resp.data if resp.data else []
    return render_template("admin/account_requests.html", requests=requests)

@admin_bp.route("/account_requests/approve/<customer_id>", methods=["POST"])
def approve_member(customer_id):
    # Approve member by customer_id
    resp = supabase.table("members").update({"status": "approved"}).eq("customer_id", customer_id).execute()
    if resp.data:
        flash("Member approved!", "success")
    else:
        flash("Member not found.", "error")
    return redirect(url_for("admin.admin_account_requests"))

@admin_bp.route("/account_requests/reject/<customer_id>", methods=["POST"])
def reject_member(customer_id):
    # Reject member by customer_id
    resp = supabase.table("members").update({"status": "rejected"}).eq("customer_id", customer_id).execute()
    if resp.data:
        flash("Member rejected.", "success")
    else:
        flash("Member not found.", "error")
    return redirect(url_for("admin.admin_account_requests"))
