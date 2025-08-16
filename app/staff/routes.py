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

@staff_bp.route('/add-transaction', methods=['POST'])
def add_transaction():
    # ...existing code to get form fields...
    customer_id = request.form.get('customer_id')
    account_number = request.form.get('account_number')
    type_ = request.form.get('type')
    amount = request.form.get('amount')
    from_account = request.form.get('from_account')
    to_account = request.form.get('to_account')
    date = request.form.get('date')
    transaction_id = request.form.get('transaction_id')
    remarks = request.form.get('remarks')

    # Get staff info from session
    staff_id = session.get('staff_id')
    staff_name = session.get('staff_name')

    # If not in session, optionally fetch staff_name from DB using staff_id
    if staff_id and not staff_name:
        staff_row = supabase.table("staff").select("name").eq("id", staff_id).execute()
        if staff_row.data and staff_row.data[0].get("name"):
            staff_name = staff_row.data[0]["name"]

    # ...existing code to calculate balance_after...

    # Insert transaction with staff_id and staff_name
    txn_data = {
        "customer_id": customer_id,
        "account_number": account_number,
        "type": type_,
        "amount": amount,
        "from_account": from_account,
        "to_account": to_account,
        "date": date if date else datetime.utcnow().isoformat(),
        "transaction_id": transaction_id,
        "remarks": remarks,
        "balance_after": 0,  # set actual balance after calculation
        "staff_id": staff_id,
        "staff_name": staff_name
    }
    # ...existing code to calculate balance_after and update txn_data...

    # Insert into transactions table
    resp = supabase.table("transactions").insert(txn_data).execute()
    if resp.data:
        return jsonify({"status": "success", "transaction": resp.data[0], "balance_after": txn_data["balance_after"]}), 201
    else:
        return jsonify({"status": "error", "message": "Failed to store transaction"}), 500
