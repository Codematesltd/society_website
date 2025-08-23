from . import core_bp
from flask import render_template
from flask import request, jsonify
from supabase import create_client
import os

@core_bp.route("/")
def home():
    return render_template("landing_page.html")

@core_bp.route("/about")
def about():
    return render_template("about.html")

@core_bp.route("/services")
def services():
    return render_template("services.html")

@core_bp.route("/contact")
def contact():
    return render_template("contact.html")


# Initialize Supabase client for core APIs
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


@core_bp.route('/api/submit-query', methods=['POST'])
def submit_query():
    try:
        data = request.get_json() or {}
        name = data.get('name')
        customer_id = data.get('customer_id') or None
        kgid = data.get('kgid') or None
        phone = data.get('phone') or None
        email = data.get('email') or None
        description = data.get('description')
        source = data.get('source') or 'web'

        if not name or not description:
            return jsonify({'status': 'error', 'message': 'name and description are required'}), 400

        record = {
            'name': name,
            'customer_id': customer_id,
            'kgid': kgid,
            'phone': phone,
            'email': email,
            'description': description,
            'source': source
        }

        resp = supabase.table('queries').insert(record).execute()
        # supabase-py returns an object where .data contains inserted rows on success
        if getattr(resp, 'data', None):
            return jsonify({'status': 'success', 'data': resp.data[0]}), 201
        # Try to extract an error message safely
        try:
            err_msg = str(resp.error)
        except Exception:
            err_msg = 'Failed to store query'
        return jsonify({'status': 'error', 'message': err_msg}), 500
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@core_bp.route('/api/queries', methods=['GET'])
def list_queries():
    """Return list of queries from Supabase ordered by newest first."""
    try:
        resp = supabase.table('queries').select('id,name,email,phone,customer_id,kgid,description,status,created_at').order('created_at', desc=True).execute()
        if getattr(resp, 'data', None) is not None:
            return jsonify({'status': 'success', 'data': resp.data}), 200
        # try to extract an error message safely
        err = getattr(resp, 'error', None) or 'Failed to fetch queries'
        return jsonify({'status': 'error', 'message': str(err)}), 500
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@core_bp.route('/api/queries/<int:qid>/mark-solved', methods=['POST'])
def mark_query_solved(qid: int):
    """Mark a query as solved by setting its status to 'solved'."""
    try:
        resp = supabase.table('queries').update({'status': 'solved'}).eq('id', qid).execute()
        if getattr(resp, 'data', None):
            return jsonify({'status': 'success', 'data': resp.data[0]}), 200
        err = getattr(resp, 'error', None) or 'Failed to update query'
        return jsonify({'status': 'error', 'message': str(err)}), 500
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
