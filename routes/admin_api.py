from flask import Blueprint, request, jsonify
from sqlalchemy import func
from .models import db, Member, Loan, LoanRecord

admin_api_bp = Blueprint('admin_api', __name__)

# ...existing code...

@admin_api_bp.route('/customer-info', methods=['GET'])
def customer_info():
    customer_id = request.args.get('customer_id')
    kgid = request.args.get('kgid')
    if not customer_id and not kgid:
        return jsonify({'status': 'error', 'message': 'customer_id or kgid required'}), 400

    # Fetch member
    member_query = db.session.query(Member)
    if customer_id:
        member_query = member_query.filter(Member.customer_id == customer_id)
    elif kgid:
        member_query = member_query.filter(Member.kgid == kgid)
    member = member_query.first()
    if not member:
        return jsonify({'status': 'error', 'message': 'Member not found'}), 404

    # Fetch loans for the member
    loans = Loan.query.filter_by(customer_id=member.customer_id).all()
    loan_list = []
    for loan in loans:
        # Calculate outstanding amount from loan_records
        outstanding = db.session.query(
            func.sum(LoanRecord.outstanding_amount)
        ).filter(LoanRecord.loan_id == loan.loan_id).scalar() or 0
        loan_list.append({
            'loan_amount': loan.loan_amount,
            'interest_rate': loan.interest_rate,
            'loan_tenure': loan.loan_term_months,
            'outstanding_amount': outstanding
        })

    result = {
        'status': 'success',
        'customer': {
            'name': member.name,
            'kgid': member.kgid,
            'customer_id': member.customer_id,
            'phone': member.phone,
            'email': member.email,
            'organization_name': member.organization_name,
            'photo_url': member.photo_url,
            'signature_url': member.signature_url
        },
        'loans': loan_list
    }
    return jsonify(result)

# ...existing code...