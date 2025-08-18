import os
from flask import Blueprint, request, jsonify, session
from supabase import create_client
from dotenv import load_dotenv

admin_api_bp = Blueprint('admin_api', __name__, url_prefix='/api')

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

@admin_api_bp.route('/member-details/<customer_id>', methods=['GET'])
def member_details(customer_id):
    """
    Get full details of a member by customer_id, including photo and signature URLs.
    """
    try:
        print(f"Fetching member details for customer_id: '{customer_id}' (length: {len(customer_id)})")
        
        # First try exact match on customer_id
        resp = supabase.table("members").select("*").eq("customer_id", customer_id).execute()
        print(f"Customer ID match response: {resp.data}")
        
        # If no match on customer_id, try email (for backwards compatibility)
        if not resp.data:
            print("Trying email match...")
            resp = supabase.table("members").select("*").eq("email", customer_id).execute()
            print(f"Email match response: {resp.data}")
        
        # If still no match, try KGID
        if not resp.data:
            print("Trying KGID match...")
            resp = supabase.table("members").select("*").eq("kgid", customer_id).execute()
            print(f"KGID match response: {resp.data}")
        
        # If still no match, try phone
        if not resp.data:
            print("Trying phone match...")
            resp = supabase.table("members").select("*").eq("phone", customer_id).execute()
            print(f"Phone match response: {resp.data}")
        
        if resp.data and len(resp.data) > 0:
            member_data = resp.data[0]
            # Ensure all expected fields are present with defaults
            member_data.setdefault('customer_id', '')
            member_data.setdefault('name', '')
            member_data.setdefault('kgid', '')
            member_data.setdefault('email', '')
            member_data.setdefault('phone', '')
            member_data.setdefault('father_name', '')
            member_data.setdefault('aadhar_no', '')
            member_data.setdefault('pan_no', '')
            member_data.setdefault('salary', '')
            member_data.setdefault('organization_name', '')
            member_data.setdefault('address', '')
            member_data.setdefault('status', 'pending')
            member_data.setdefault('balance', 0)
            member_data.setdefault('photo_url', '')
            member_data.setdefault('signature_url', '')
            member_data.setdefault('created_at', '')
            
            return jsonify({
                "status": "success", 
                "member": member_data
            }), 200
        else:
            # Debug: List all pending members
            all_resp = supabase.table("members").select("customer_id, email, kgid, phone, name").eq("status", "pending").execute()
            all_data = [f"{m.get('name', 'No Name')} (ID: {m.get('customer_id', 'No ID')}, Email: {m.get('email', 'No Email')}, KGID: {m.get('kgid', 'No KGID')}, Phone: {m.get('phone', 'No Phone')})" for m in all_resp.data]
            print(f"All pending members: {all_data}")
            return jsonify({
                "status": "error",
                "message": f"Member not found for identifier: {customer_id}",
                "debug_pending_members": all_data
            }), 404
    except Exception as e:
        print(f"Exception in member_details: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": f"Database error: {str(e)}"
        }), 500

@admin_api_bp.route('/debug-pending-members', methods=['GET'])
def debug_pending_members():
    """
    List all pending members and their customer_id for debugging.
    """
    resp = supabase.table("members").select("id, name, customer_id, status").eq("status", "pending").execute()
    return jsonify(resp.data), 200
