from flask import Blueprint, jsonify, current_app, request, session
import os
import requests

bp_expenses = Blueprint('check_expenses_api', __name__)

# --- STAFF: Add Expense (POST) ---
@bp_expenses.route('/api/staff/add-expense', methods=['POST'])
def staff_add_expense():
    """
    POST: Insert a new expense into 'expenses' table.
    Expects JSON: { name, amount, date, description, transaction_id }
    """
    SUPABASE_URL = os.getenv('SUPABASE_URL') or current_app.config.get('SUPABASE_URL')
    SUPABASE_KEY = os.getenv('SUPABASE_KEY') or current_app.config.get('SUPABASE_KEY')
    if not SUPABASE_URL or not SUPABASE_KEY:
        return jsonify(status='error', message='SUPABASE_URL and SUPABASE_KEY must be set'), 500

    base_url = SUPABASE_URL.rstrip('/') + '/rest/v1/expenses'
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

    payload = request.get_json(silent=True)
    if not payload:
        return jsonify(status='error', message='Invalid JSON payload'), 400

    name = payload.get('name')
    amount = payload.get('amount')
    date = payload.get('date')  # expected ISO date YYYY-MM-DD
    description = payload.get('description') or payload.get('remarks') or None
    transaction_id = payload.get('transaction_id') or None

    # --- Check required fields ---
    if not name or amount in (None, '') or not date:
        return jsonify(status='error', message='Missing required fields: name, amount, date'), 400

    # --- Get staff email from session ---
    staff_email = session.get('staff_email') or session.get('email')

    # --- Build insert object matching your table columns ---
    insert_obj = {
        "name": name,
        "amount": float(amount),
        "date": date,
        "description": description,
        "transaction_id": transaction_id,
        "created_by": staff_email  # Store staff email who created the expense
    }

    try:
        resp = requests.post(base_url, json=insert_obj, headers=headers, timeout=10)
        if resp.status_code in (200, 201):
            created = resp.json()
            return jsonify(status='success', expense=created), 201
        else:
            try:
                server_msg = resp.json()
            except Exception:
                server_msg = resp.text or resp.reason
            return jsonify(status='error', message='Supabase insert failed', supabase_error=server_msg), 500
    except requests.exceptions.RequestException as e:
        return jsonify(status='error', message='Connection error: ' + str(e)), 502

# --- ADMIN: List Expenses (GET) ---
@bp_expenses.route('/api/admin/list-expenses', methods=['GET'])
def admin_list_expenses():
    """
    GET: Returns expenses list from Supabase PostgREST.
    """
    SUPABASE_URL = os.getenv('SUPABASE_URL') or current_app.config.get('SUPABASE_URL')
    SUPABASE_KEY = os.getenv('SUPABASE_KEY') or current_app.config.get('SUPABASE_KEY')
    if not SUPABASE_URL or not SUPABASE_KEY:
        return jsonify(status='error', message='SUPABASE_URL and SUPABASE_KEY must be set'), 500

    base_url = SUPABASE_URL.rstrip('/') + '/rest/v1/expenses'
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

    try:
        params = {"select": "*", "order": "date.desc", "limit": "100"}
        resp = requests.get(base_url, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        expenses = resp.json()
        return jsonify(status='success', expenses=expenses)
    except requests.exceptions.RequestException as e:
        return jsonify(status='error', message='Supabase fetch failed: ' + str(e)), 502
    except Exception as ex:
        return jsonify(status='error', message='Unexpected error: ' + str(ex)), 500
