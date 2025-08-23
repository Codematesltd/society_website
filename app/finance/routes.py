from . import finance_bp

@finance_bp.route("/dashboard")
def dashboard():
    return "<h1>Finance Dashboard</h1>"

# Loan Repayment Endpoint
from flask import request, jsonify
import math
import os

# bring in supabase client used by finance APIs
from .api import supabase

@finance_bp.route('/api/loan/repay', methods=['POST'])
def loan_repay():
    data = request.get_json()
    loan_id = data.get('loan_id')
    amount = data.get('amount')
    if not loan_id or not amount:
        return jsonify({'message': 'Missing loan_id or amount'}), 400
    # TODO: Implement actual repayment logic
    return jsonify({'message': 'Repayment successful!'}), 200

# Next Installment Endpoint
@finance_bp.route('/api/loan/next-installment', methods=['GET'])
def next_installment():
    loan_id = request.args.get('loan_id')
    if not loan_id:
        return jsonify({'message': 'Missing loan_id'}), 400
    # TODO: Implement actual next installment logic
    return jsonify({
        'next_installment': 5000,
        'due_date': '2025-09-10',
        'status': 'Pending'
    }), 200


# Compatibility route for templates that call /api/next-installment
@finance_bp.route('/api/next-installment', methods=['GET'])
def next_installment_compat():
    """Compatibility wrapper that accepts ?account=... and returns the keys the UI expects.
    It delegates to the existing next_installment() handler when possible and maps fields.
    """
    # Accept either 'account' or 'loan_id'
    account = request.args.get('account') or request.args.get('loan_id')
    if not account:
        return jsonify({'message': 'Missing account parameter'}), 400

    # Determine whether the provided value is a loan identifier or a customer id
    loan_id = request.args.get('loan_id')
    customer_id = None
    if not loan_id:
        # If query param named 'customer_id' provided, use it; otherwise treat 'account' as customer_id
        customer_id = request.args.get('customer_id') or request.args.get('account')

    # If we have customer_id, try to find the latest approved loan for that customer
    loan_row = None
    import traceback
    try:
        if not loan_id and customer_id:
            loans_resp = supabase.table('loans').select('*').eq('customer_id', customer_id).order('created_at', desc=True).execute()
            if loans_resp.data and len(loans_resp.data) > 0:
                # pick the most recent loan (prefer approved/active if available)
                # try to find approved first
                approved = [l for l in loans_resp.data if l.get('status') in ('approved', 'active')]
                loan_row = (approved[0] if approved else loans_resp.data[0])
                loan_id = loan_row.get('loan_id') or loan_row.get('id')
        elif loan_id:
            # fetch loan by textual loan_id or UUID
            # If loan_id looks like a UUID, include id.eq comparison; otherwise query by loan_id only
            import re
            uuid_regex = re.compile(r"^[0-9a-fA-F-]{32,36}$")
            try:
                if uuid_regex.match(str(loan_id)):
                    # loan_id is a UUID-like value
                    loan_resp = supabase.table('loans').select('*').or_(f"id.eq.{loan_id},loan_id.eq.{loan_id}").limit(1).execute()
                else:
                    # textual loan id like LN0002 — query by loan_id only to avoid uuid parsing errors
                    loan_resp = supabase.table('loans').select('*').eq('loan_id', loan_id).limit(1).execute()
                if loan_resp.data:
                    loan_row = loan_resp.data[0]
            except Exception as e:
                # Bubble up DB errors to outer handler
                raise
    except Exception as e:
        tb = traceback.format_exc()
        print("[ERROR] Exception in next_installment_compat:\n", tb)
        # Return traceback in response for debugging (only in dev)
        return jsonify({'message': 'Error querying loans', 'error': str(e), 'traceback': tb}), 500

    if not loan_row:
        return jsonify({'message': 'Loan not found for provided account/loan_id'}), 404

    # Compute amounts
    def safe_float(v):
        try:
            return float(v) if v is not None else 0.0
        except Exception:
            return 0.0

    # Start with any loan_amount present on the row, but prefer a fresh authoritative value from loans table
    principal = safe_float(loan_row.get('loan_amount'))
    try:
        loan_id_text = loan_row.get('loan_id')
        loan_uuid = loan_row.get('id')
        loan_amount_val = None
        # Try by textual loan_id first (safe for LN0002)
        if loan_id_text:
            resp = supabase.table('loans').select('loan_amount').eq('loan_id', loan_id_text).limit(1).execute()
            if resp.data and len(resp.data) > 0:
                loan_amount_val = resp.data[0].get('loan_amount')
        # Fallback: try by UUID
        if loan_amount_val is None and loan_uuid:
            resp2 = supabase.table('loans').select('loan_amount').eq('id', loan_uuid).limit(1).execute()
            if resp2.data and len(resp2.data) > 0:
                loan_amount_val = resp2.data[0].get('loan_amount')
        if loan_amount_val is not None:
            principal = safe_float(loan_amount_val)
    except Exception:
        # Keep the previously read principal if any and continue
        pass

    # Sum repayments from loan_records by querying both possible loan_id values safely (avoid OR with non-UUIDs)
    paid = 0.0
    try:
        recs = []
        if loan_id_text:
            r1 = supabase.table('loan_records').select('repayment_amount,id').eq('loan_id', loan_id_text).execute()
            if r1.data:
                recs.extend(r1.data)
        if loan_uuid and loan_uuid != loan_id_text:
            r2 = supabase.table('loan_records').select('repayment_amount,id').eq('loan_id', loan_uuid).execute()
            if r2.data:
                recs.extend(r2.data)
        # Sum repayments (deduplicate by record id if present)
        seen = set()
        for r in recs:
            rid = r.get('id')
            if rid and rid in seen:
                continue
            if rid:
                seen.add(rid)
            paid += safe_float(r.get('repayment_amount'))
    except Exception:
        paid = 0.0

    remaining = max(principal - paid, 0.0)

    # Estimate next month installment (EMI-like) using remaining and remaining months if available
    months = int(loan_row.get('loan_term_months') or 0)
    interest_rate = safe_float(loan_row.get('interest_rate') or 0.0)
    next_month_amount = 0.0
    try:
        if remaining <= 0:
            next_month_amount = 0.0
        else:
            remaining_months = months if months > 0 else 1
            monthly_rate = interest_rate / (12 * 100)
            if monthly_rate > 0 and remaining_months > 0:
                r = monthly_rate
                n = remaining_months
                # standard EMI formula applied to remaining principal
                emi = remaining * (r * (1 + r) ** n) / ((1 + r) ** n - 1)
                next_month_amount = round(emi, 2)
            else:
                next_month_amount = round(remaining / remaining_months, 2)
    except Exception:
        next_month_amount = round(remaining if remaining > 0 else 0.0, 2)

    result = {
        'loanAmount': principal,
        'paidAmount': round(paid, 2),
        'remainingAmount': round(remaining, 2),
        'nextMonthAmount': next_month_amount,
        'status': loan_row.get('status') or 'unknown',
        'loan_id': loan_id_text
    }
    return jsonify(result), 200

# Check Transaction Endpoint
@finance_bp.route('/staff/transaction/check/<stid>', methods=['GET'])
def check_transaction(stid):
    # TODO: Implement actual transaction lookup
    return jsonify({
        'transaction_id': stid,
        'amount': 10000,
        'status': 'Success',
        'date': '2025-08-01'
    }), 200
