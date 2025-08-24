import os
from flask import Blueprint, request, jsonify, session

from supabase import create_client
from dotenv import load_dotenv
from datetime import datetime

admin_api_bp = Blueprint('admin_api', __name__, url_prefix='/admin/api')

# Load environment variables
load_dotenv()

# Supabase setup
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

@admin_api_bp.route('/loan-info', methods=['GET'])
def loan_info():
    """
    Get loan info by loan_id only.
    Query params: loan_id (required)
    Returns: Name, loan_amount, loan_term_months, interest_rate, next_installment_amount, outstanding_amount
    """
    loan_id = request.args.get('loan_id')
    if not loan_id:
        return jsonify({'status': 'error', 'message': 'loan_id is required'}), 400
    try:
        # Fetch loan by loan_id
        loan_query = supabase.table("loans").select("*").filter("loan_id", "eq", loan_id)
        loan_resp = loan_query.limit(1).execute()
        if not loan_resp.data or len(loan_resp.data) == 0:
            return jsonify({'status': 'error', 'message': 'Loan not found'}), 404
        loan = loan_resp.data[0]
        # Fetch member name
        member_resp = supabase.table("members").select("name").filter("customer_id", "eq", loan["customer_id"]).limit(1).execute()
        name = member_resp.data[0]["name"] if member_resp.data and len(member_resp.data) > 0 else None
        # Fetch loan records for next installment and outstanding
        records_resp = supabase.table("loan_records").select("repayment_date,repayment_amount,outstanding_balance").filter("loan_id", "eq", loan["loan_id"]).order("repayment_date").execute()
        records = records_resp.data if hasattr(records_resp, 'data') else []
        # Find next installment (first record with outstanding_balance > 0 and repayment_amount is null or 0)
        next_installment = None
        outstanding_amount = None
        for rec in records:
            if (rec.get('repayment_amount') is None or float(rec.get('repayment_amount') or 0) == 0) and float(rec.get('outstanding_balance') or 0) > 0:
                next_installment = rec.get('outstanding_balance')
                break
        # Outstanding = last non-null outstanding_balance
        for rec in reversed(records):
            if rec.get('outstanding_balance') is not None:
                outstanding_amount = rec.get('outstanding_balance')
                break
        # If no loan_records, outstanding = loan_amount
        if outstanding_amount is None:
            outstanding_amount = loan.get('loan_amount')
        # If no next_installment, set to 0
        if next_installment is None:
            next_installment = 0
        result = {
            'name': name,
            'loan_amount': loan.get('loan_amount'),
            'loan_term_months': loan.get('loan_term_months'),
            'interest_rate': loan.get('interest_rate'),
            'next_installment_amount': float(next_installment),
            'outstanding_amount': float(outstanding_amount)
        }
        return jsonify({'status': 'success', 'loan_info': result}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# List staff salaries with pagination
@admin_api_bp.route('/list-staff-salaries', methods=['GET'])
def list_staff_salaries():
    """
    List staff salaries with pagination. Query params: page, page_size
    """
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 10))
        offset = (page - 1) * page_size
        # Get total count
        total_resp = supabase.table("staff_salaries").select('id', count='exact').execute()
        total = total_resp.count if hasattr(total_resp, 'count') else 0
        # Get paginated data, order by date desc, id desc
        resp = supabase.table("staff_salaries") \
            .select("name,kgid,salary,to_account,from_account,transaction_id,date") \
            .order("date", desc=True) \
            .order("id", desc=True) \
            .range(offset, offset + page_size - 1) \
            .execute()
        salaries = resp.data if hasattr(resp, 'data') else []
        return jsonify({
            'status': 'success',
            'salaries': salaries,
            'total': total
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@admin_api_bp.route('/account-requests', methods=['GET'])
def get_account_requests():
    """
    Get all pending account requests.
    """
    try:
        response = supabase.table("members") \
            .select("name,email,phone,kgid,created_at") \
            .eq("status", "pending") \
            .execute()
        
        return jsonify({
            'status': 'success',
            'members': response.data
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@admin_api_bp.route('/approve-member', methods=['POST'])
def approve_member():
    """
    Approve a pending account request.
    """
    email = request.form.get('email')
    if not email:
        return jsonify({
            'status': 'error',
            'message': 'Email is required'
        }), 400
    
    try:
        # Update member status to approved
        response = supabase.table("members") \
            .update({"status": "approved"}) \
            .eq("email", email) \
            .execute()
        
        if not response.data or len(response.data) == 0:
            return jsonify({
                'status': 'error',
                'message': 'Member not found'
            }), 404
        
        # Send approval email
        try:
            # Try to import and use the send_status_email function
            from app.manager.api import send_status_email
            send_status_email(email, "approved")
        except Exception as e:
            # Continue even if email sending fails
            print(f"Error sending approval email: {e}")
            
        return jsonify({
            'status': 'success',
            'message': 'Member approved successfully'
        }, 200)
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@admin_api_bp.route('/reject-member', methods=['POST'])
def reject_member():
    """
    Reject a pending account request.
    """
    email = request.form.get('email')
    if not email:
        return jsonify({
            'status': 'error',
            'message': 'Email is required'
        }), 400
    
    try:
        # Update member status to rejected
        response = supabase.table("members") \
            .update({"status": "rejected"}) \
            .eq("email", email) \
            .execute()
        
        if not response.data or len(response.data) == 0:
            return jsonify({
                'status': 'error',
                'message': 'Member not found'
            }), 404
        
        # Send rejection email
        try:
            # Try to import and use the send_status_email function
            from app.manager.api import send_status_email
            send_status_email(email, "rejected")
        except Exception as e:
            # Continue even if email sending fails
            print(f"Error sending rejection email: {e}")
            
        return jsonify({
            'status': 'success',
            'message': 'Member rejected successfully'
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@admin_api_bp.route('/add-staff-salary', methods=['POST'])
def add_staff_salary():
    """
    Add a new staff salary record.
    Required fields: name, kgid, salary, to_account, from_account, transaction_id, date
    """
    data = request.get_json() or request.form
    required_fields = ["name", "kgid", "salary", "to_account", "from_account", "transaction_id", "date"]
    missing = [f for f in required_fields if not data.get(f)]
    if missing:
        return jsonify({
            'status': 'error',
            'message': f"Missing fields: {', '.join(missing)}"
        }), 400

    try:
        # Insert into staff_salaries table
        response = supabase.table("staff_salaries").insert({
            "name": data["name"],
            "kgid": data["kgid"],
            "salary": float(data["salary"]),
            "to_account": data["to_account"],
            "from_account": data["from_account"],
            "transaction_id": data["transaction_id"],
            "date": data["date"]
        }).execute()
        if response.data:
            return jsonify({
                'status': 'success',
                'message': 'Staff salary added successfully',
                'record': response.data[0]
            }), 201
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to add staff salary'
            }), 500
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@admin_api_bp.route('/member-details/<email>', methods=['GET'])
def member_details(email):
    """
    Get full member details by email only.
    """
    try:
        resp = supabase.table("members").select(
            "customer_id, name, kgid, email, phone, aadhar_no, pan_no, salary, organization_name, address, status, balance, created_at, photo_url, signature_url"
        ).eq("email", email).execute()
        
        if resp.data and len(resp.data) > 0:
            return jsonify({"status": "success", "member": resp.data[0]}), 200
        
        return jsonify({"status": "error", "message": "Member not found"}), 404
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@admin_api_bp.route('/customer-info', methods=['GET'])
def customer_info():
    """
    Get customer info by customer_id or kgid.
    Returns: name, kgid, customer_id, phone, email, organization_name, photo_url, signature_url from members,
             loan_amount, interest_rate, loan_tenure from loans,
             outstanding_amount from loan_records.
    """
    customer_id = request.args.get('customer_id')
    kgid = request.args.get('kgid')
    # Only allow search by customer_id for security and clarity
    if not customer_id:
        return jsonify({'status': 'error', 'message': 'customer_id required'}), 400
    try:
        # Fetch member
        member_query = supabase.table("members").select(
            "name,kgid,customer_id,phone,email,organization_name,photo_url,signature_url"
        ).eq("customer_id", customer_id)
        member_resp = member_query.limit(1).execute()
        if not member_resp.data or len(member_resp.data) == 0:
            return jsonify({'status': 'error', 'message': 'Member not found'}), 404
        member = member_resp.data[0]

        # Fetch loans for the member
        loans_resp = supabase.table("loans").select(
            "loan_id,loan_amount,interest_rate,loan_term_months,loan_type,status,created_at"
        ).eq("customer_id", member["customer_id"]).execute()
        loans = loans_resp.data if hasattr(loans_resp, 'data') else []

        # For each loan, fetch outstanding_amount from loan_records
        loan_list = []
        for loan in loans:
            records_resp = supabase.table("loan_records").select("outstanding_balance").eq("loan_id", loan["loan_id"]).order("repayment_date").execute()
            outstanding = None
            if records_resp.data and len(records_resp.data) > 0:
                # Get last non-null outstanding_balance
                for rec in reversed(records_resp.data):
                    if rec.get("outstanding_balance") is not None:
                        outstanding = rec["outstanding_balance"]
                        break
            if outstanding is None:
                outstanding = loan.get("loan_amount", 0)
            loan_list.append({
                "loan_id": loan.get("loan_id"),
                "loan_amount": loan.get("loan_amount"),
                "interest_rate": loan.get("interest_rate"),
                "loan_tenure": loan.get("loan_term_months"),
                "loan_type": loan.get("loan_type"),
                "status": loan.get("status"),
                "created_at": loan.get("created_at"),
                "outstanding_amount": float(outstanding)
            })

        return jsonify({
            "status": "success",
            "customer": member,
            "loans": loan_list
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@admin_api_bp.route('/member-details-by-kgid', methods=['GET'])
def member_details_by_kgid():
    kgid = request.args.get('kgid')
    if not kgid:
        return jsonify({'status': 'error', 'message': 'kgid required'}), 400
    try:
        resp = supabase.table("members").select("customer_id,kgid").eq("kgid", kgid).limit(1).execute()
        if resp.data and len(resp.data) > 0:
            return jsonify({'status': 'success', 'member': resp.data[0]}), 200
        return jsonify({'status': 'error', 'message': 'KGID not found'}), 404
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
       

