from flask import Blueprint, jsonify, current_app
import os
import requests

bp_expenses = Blueprint('check_expenses_api', __name__)

@bp_expenses.route('/api/check-expenses', methods=['GET'])
def check_expenses():
    """
    Returns expenses list from Supabase PostgREST.
    Expects environment variables:
      SUPABASE_URL (e.g. https://xxxx.supabase.co)
      SUPABASE_KEY (service_role or anon key)
    """
    SUPABASE_URL = os.getenv('SUPABASE_URL') or current_app.config.get('SUPABASE_URL')
    SUPABASE_KEY = os.getenv('SUPABASE_KEY') or current_app.config.get('SUPABASE_KEY')

    if not SUPABASE_URL or not SUPABASE_KEY:
        return jsonify(status='error', message='SUPABASE_URL and SUPABASE_KEY must be set'), 500

    # Query the 'expenses' table (adjust table name/fields if yours differs)
    try:
        url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/expenses"
        # select all fields, limit 100 by default, order by date desc if present
        params = {
            "select": "*",
            "order": "date.desc",
            "limit": "100"
        }
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}"
        }
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        expenses = resp.json()
        return jsonify(status='success', expenses=expenses)
    except requests.exceptions.RequestException as e:
        return jsonify(status='error', message='Failed to fetch from Supabase: ' + str(e)), 502
    except Exception as ex:
        return jsonify(status='error', message='Unexpected error: ' + str(ex)), 500
