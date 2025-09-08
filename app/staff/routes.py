from . import staff_bp
from flask import render_template, request, jsonify, session
from supabase import create_client
import os
from datetime import datetime

@staff_bp.route("/dashboard")
def dashboard():
    return render_template("staff_dashboard.html")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


@staff_bp.route('/api/get-customer')
def get_customer():
    customer_id = request.args.get('customer_id')
    if not customer_id:
        return jsonify({"error": "Missing customer_id"}), 400

    # Query members table for customer info
    result = supabase.table("members").select("customer_id, name, balance, share_amount").eq("customer_id", customer_id).execute()
    if result.data and len(result.data) > 0:
        customer = result.data[0]
        # Return all expected fields for frontend
        return jsonify({
            "customer_id": customer.get("customer_id"),
            "name": customer.get("name"),
            "balance": customer.get("balance", 0),
            "share_amount": customer.get("share_amount", 0)
        }), 200
    else:
        # Make sure error key is 'name' for frontend check
        return jsonify({
            "name": None,
            "customer_id": customer_id,
            "balance": 0,
            "share_amount": 0,
            "error": "Customer not found"
        }), 404

@staff_bp.route('/api/customer')
def api_customer():
    kgid = request.args.get('kgid')
    if not kgid:
        return jsonify({
            "name": None,
            "kgid": None,
            "error": "Missing KGID"
        }), 200

    # Query members table for customer info by KGID (case-insensitive)
    result = supabase.table("members").select(
        "customer_id, kgid, name, phone, email, address, balance, share_amount"
    ).eq("kgid", kgid).execute()

    if result.data and len(result.data) > 0:
        customer = result.data[0]
        return jsonify({
            "customer_id": customer.get("customer_id"),
            "kgid": customer.get("kgid"),
            "name": customer.get("name"),
            "phone": customer.get("phone"),
            "email": customer.get("email"),
            "address": customer.get("address"),
            "balance": customer.get("balance", 0),
            "share_amount": customer.get("share_amount", 0)
        }), 200
    else:
        # Not found, always return 200 and name=None for frontend
        return jsonify({
            "customer_id": None,
            "kgid": kgid,
            "name": None,
            "phone": None,
            "email": None,
            "address": None,
            "balance": 0,
            "share_amount": 0,
            "error": "Customer not found"
        }), 200