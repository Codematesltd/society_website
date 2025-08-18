from . import finance_bp

@finance_bp.route("/dashboard")
def dashboard():
    return "<h1>Finance Dashboard</h1>"

# Loan Repayment Endpoint
from flask import request, jsonify

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
