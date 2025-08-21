from flask import Blueprint, jsonify, current_app, request
import os
import requests
import json
from pathlib import Path
from datetime import datetime

bp_expenses = Blueprint('check_expenses_api', __name__)

# Local fallback storage (used when Supabase is not configured or insert fails)
REPO_ROOT = Path(__file__).resolve().parent.parent
LOCAL_DATA_DIR = REPO_ROOT / 'data'
LOCAL_DATA_DIR.mkdir(parents=True, exist_ok=True)
LOCAL_STORE = LOCAL_DATA_DIR / 'expenses_local.json'

def read_local_expenses():
    try:
        if not LOCAL_STORE.exists():
            return []
        with LOCAL_STORE.open('r', encoding='utf-8') as f:
            return json.load(f) or []
    except Exception:
        return []

def append_local_expense(obj):
    try:
        arr = read_local_expenses()
        arr.insert(0, obj)
        with LOCAL_STORE.open('w', encoding='utf-8') as f:
            json.dump(arr, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False

@bp_expenses.route('/api/check-expenses', methods=['GET', 'POST'])
def check_expenses():
    """
    GET: Returns expenses list from Supabase PostgREST.
    POST: Insert a new expense into 'expenses' table.
    Expects environment variables:
      SUPABASE_URL (e.g. https://xxxx.supabase.co)
      SUPABASE_KEY (service_role or anon key)
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
        # return the created row on insert
        "Prefer": "return=representation"
    }

    # GET - fetch list
    if request.method == 'GET':
        try:
            params = {"select": "*", "order": "date.desc", "limit": "100"}
            resp = requests.get(base_url, params=params, headers=headers, timeout=10)
            resp.raise_for_status()
            expenses = resp.json()
            # Merge with local fallback expenses (local entries first)
            local = read_local_expenses()
            combined = local + (expenses or [])
            return jsonify(status='success', expenses=combined)
        except requests.exceptions.RequestException as e:
            # If Supabase fetch failed, return local store so staff entries are visible
            local = read_local_expenses()
            return jsonify(status='success', expenses=local, message='Supabase fetch failed, showing local entries'), 200
        except Exception as ex:
            return jsonify(status='error', message='Unexpected error: ' + str(ex)), 500

    # POST - insert new expense
    try:
        payload = request.get_json(silent=True)
        if not payload:
            return jsonify(status='error', message='Invalid JSON payload'), 400

        # basic validation: require name, amount, date
        name = payload.get('name')
        amount = payload.get('amount')
        date = payload.get('date')  # expected ISO date YYYY-MM-DD
        description = payload.get('description') or payload.get('remarks') or None
        transaction_id = payload.get('transaction_id') or None

        if not name or amount in (None, '') or not date:
            return jsonify(status='error', message='Missing required fields: name, amount, date'), 400

        # build insert object - adjust keys if your Supabase table uses different column names
        insert_obj = {
            "name": name,
            "amount": float(amount),
            "date": date,
            "description": description,
            "transaction_id": transaction_id
        }

        try:
            resp = requests.post(base_url, json=insert_obj, headers=headers, timeout=10)
            # If PostgREST returns 201 or 200 with representation, parse it
            if resp.status_code in (200, 201):
                created = resp.json()
                return jsonify(status='success', expense=created), 201
            else:
                # try to capture server message
                try:
                    server_msg = resp.json()
                except Exception:
                    server_msg = resp.text or resp.reason
                # fallback: store locally and return success with fallback flag
                insert_obj['_created_local_at'] = datetime.utcnow().isoformat()
                append_local_expense(insert_obj)
                return jsonify(status='success', expense=insert_obj, message='Saved locally; Supabase insert failed', supabase_error=server_msg), 201
        except requests.exceptions.RequestException as e:
            # network failure -> store locally
            insert_obj['_created_local_at'] = datetime.utcnow().isoformat()
            append_local_expense(insert_obj)
            return jsonify(status='success', expense=insert_obj, message='Saved locally due to connection error'), 201

    except requests.exceptions.RequestException as e:
        return jsonify(status='error', message='Failed to connect to Supabase: ' + str(e)), 502
    except Exception as ex:
        return jsonify(status='error', message='Unexpected error: ' + str(ex)), 500
