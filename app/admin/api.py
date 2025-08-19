import os
from flask import Blueprint, request, jsonify, session
from supabase import create_client
from dotenv import load_dotenv

admin_api_bp = Blueprint('admin_api', __name__, url_prefix='/admin/api')

# Load environment variables
load_dotenv()

# Supabase setup
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

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
