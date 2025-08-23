from flask import request, jsonify
from . import finance_bp

@finance_bp.route('/api/check-civil-score', methods=['GET'])
def check_civil_score():
    # Expecting ?customer_id=XYZ or ?kgid=XYZ
    customer_id = request.args.get('customer_id') or request.args.get('kgid')
    if not customer_id:
        return jsonify(status='error', message='Missing customer_id'), 400

    # TODO: Replace with real lookup logic (DB or external service)
    # For now, return a dummy civil score
    dummy_score = 720  # placeholder value

    return jsonify(
        status='success',
        customer_id=customer_id,
        civil_score=dummy_score
    )