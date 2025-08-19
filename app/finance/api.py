from flask import request, jsonify, render_template, make_response, abort, session, url_for
import os
import uuid
import re
from supabase import create_client, Client
from dotenv import load_dotenv
import pdfkit
import inflect
import smtplib
from email.mime.text import MIMEText
from datetime import datetime

from . import finance_bp
from app.auth.routes import notify_admin_loan_application

load_dotenv()
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
p = inflect.engine()

def generate_loan_id():
    """Generate a unique loan ID in format LNXXXX"""
    try:
        # Get the highest existing loan number
        result = supabase.table("loans").select("loan_id").execute()
        
        highest_num = 0
        if result.data:
            for loan in result.data:
                loan_id = loan.get("loan_id", "")
                if loan_id and loan_id.startswith("LN"):
                    try:
                        num = int(loan_id[2:])
                        highest_num = max(highest_num, num)
                    except ValueError:
                        pass
        
        # Increment and format with leading zeros
        next_num = highest_num + 1
        return f"LN{next_num:04d}"
    except Exception as e:
        print(f"Error generating loan ID: {e}")
        # Fallback to timestamp-based ID if database query fails
        return f"LN{int(datetime.now().timestamp())%10000:04d}"

def get_member_by_customer_id(customer_id):
    resp = supabase.table("members").select("customer_id,name,phone,signature_url,photo_url").eq("customer_id", customer_id).execute()
    return resp.data[0] if resp.data else None

def get_staff_by_email(email):
    """Fetch staff record by email."""
    # return phone instead of photo/signature so we store name + phone only
    resp = supabase.table("staff").select("email,name,phone").eq("email", email).execute()
    return resp.data[0] if resp.data else None

def amount_to_words(amount):
    try:
        n = int(float(amount))
        words = p.number_to_words(n, andword='').replace(',', '')
        return words.title() + " Rupees Only"
    except Exception:
        return str(amount)

def send_loan_status_email(email, name, loan_id, status):
    EMAIL_USER = os.environ.get("EMAIL_USER")
    EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
    if not EMAIL_USER or not EMAIL_PASSWORD:
        return
    if status == "pending":
        subject = "Loan Application Submitted"
        body = f"Dear {name},\n\nYour loan application (ID: {loan_id}) has been submitted and is pending manager approval.\n\nYou can download your loan certificate here:\n{os.environ.get('BASE_URL', 'http://127.0.0.1:5000')}/finance/certificate/{loan_id}?action=view\n\nThank you."
    elif status == "approved":
        subject = "Loan Application Approved"
        body = f"Dear {name},\n\nYour loan application (ID: {loan_id}) has been approved.\n\nThank you."
    elif status == "rejected":
        subject = "Loan Application Rejected"
        body = f"Dear {name},\n\nYour loan application (ID: {loan_id}) has been rejected.\n\nThank you."
    else:
        subject = "Loan Status Update"
        body = f"Dear {name},\n\nYour loan application (ID: {loan_id}) status: {status}\n\nThank you."
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = EMAIL_USER
    msg['To'] = email
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        print(f"Failed to send loan status email: {e}")

@finance_bp.route('/apply', methods=['POST'])
def apply_loan():
    """
    Handle loan application submissions
    """
    try:
        # Get JSON data from request
        data = request.get_json() or {}
        
        # Validate required fields
        required_fields = ["loan_type", "customer_id", "loan_amount", "interest_rate", "loan_term_months", "sureties"]
        for field in required_fields:
            if field not in data:
                return jsonify({"status": "error", "message": f"Missing required field: {field}"}), 400
        
        # Extract sureties from request data before creating loan record
        sureties = data.get("sureties", [])
        
        # Generate a unique loan ID in format LNXXXX
        loan_id = generate_loan_id()
        
        # Prepare loan data - removed sureties field as it doesn't exist in schema
        loan_data = {
            "loan_id": loan_id,
            "customer_id": data["customer_id"],
            "loan_type": data["loan_type"],
            "loan_amount": data["loan_amount"],
            "interest_rate": data["interest_rate"],
            "loan_term_months": data["loan_term_months"],
            "status": "pending_approval"
        }
        
        # Add optional fields based on loan type
        if data["loan_type"] == "normal" and "purpose_of_loan" in data:
            loan_data["purpose_of_loan"] = data["purpose_of_loan"]
        elif data["loan_type"] == "emergency" and "purpose_of_emergency_loan" in data:
            loan_data["purpose_of_emergency_loan"] = data["purpose_of_emergency_loan"]
        
        # Get staff email from session
        staff_email = session.get("email")
        if staff_email:
            loan_data["staff_email"] = staff_email
        
        # Insert loan application in database
        result = supabase.table("loans").insert(loan_data).execute()
        
        if not result.data:
            return jsonify({"status": "error", "message": "Failed to submit loan application"}), 500
        
        # Get the created loan ID from the response
        created_loan_id = result.data[0].get("id")
        
        # Store sureties in separate table
        if sureties and created_loan_id:
            for surety_id in sureties:
                # Get surety details from members table
                surety_member = supabase.table("members") \
                    .select("name,phone,signature_url,photo_url") \
                    .eq("customer_id", surety_id) \
                    .execute()
                
                if not surety_member.data or len(surety_member.data) == 0:
                    print(f"Warning: Surety with ID {surety_id} not found in members table")
                    continue
                
                surety_info = surety_member.data[0]
                
                surety_data = {
                    "loan_id": created_loan_id,
                    "surety_customer_id": surety_id,
                    "surety_name": surety_info.get("name", "Unknown"),
                    "surety_mobile": surety_info.get("phone", "0000000000"),  # Required field
                    "surety_signature_url": surety_info.get("signature_url"),
                    "surety_photo_url": surety_info.get("photo_url"),
                    "active": False  # Sureties become active only after loan approval
                }
                
                # Insert surety into sureties table
                surety_result = supabase.table("sureties").insert(surety_data).execute()
                if not surety_result.data:
                    print(f"Warning: Failed to insert surety {surety_id} for loan {loan_id}")
        
        # Notify administrators about the new loan application
        notify_admin_loan_application(
            loan_id=loan_id,
            customer_id=data["customer_id"],
            loan_type=data["loan_type"],
            amount=data["loan_amount"]
        )
        
        # Build certificate URL
        certificate_url = url_for('finance.loan_certificate', 
                                  loan_id=loan_id,
                                  action='view', 
                                  _external=True)
        
        # Return success with loan_id and certificate URL
        return jsonify({
            "status": "success", 
            "message": "Loan application submitted successfully and is pending approval",
            "loan_id": loan_id,
            "certificate_url": certificate_url
        }), 200
    
    except Exception as e:
        print(f"Error in apply_loan: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@finance_bp.route('/<loan_id>', methods=['GET'])
def get_loan(loan_id):
    loan = supabase.table("loans").select("*").eq("id", loan_id).execute()
    if not loan.data:
        return jsonify({"status": "error", "message": "Loan not found"}), 404
    loan_data = loan.data[0]
    # Fetch customer details
    customer = supabase.table("members").select("customer_id,name,phone,photo_url,signature_url").eq("customer_id", loan_data["customer_id"]).execute()
    # Fetch sureties
    sureties = supabase.table("sureties").select("*").eq("loan_id", loan_id).execute()
    # Fetch loan records
    records = supabase.table("loan_records").select("*").eq("loan_id", loan_id).execute()
    # Fetch staff details (already in loan_data, but can be refreshed if needed)
    staff_details = {
        "email": loan_data.get("staff_email"),
        "name": loan_data.get("staff_name"),
        # expose phone (no photo/signature)
        "phone": loan_data.get("staff_phone")
    }
    # Fixed: Properly formatted return statement
    return jsonify({
        "status": "success",
        "loan": loan_data,
        "customer": customer.data[0] if customer.data else {},
        "sureties": sureties.data,
        "records": records.data,
        "staff": staff_details
    }), 200

@finance_bp.route('/approve/<loan_id>', methods=['POST'])
def approve_loan(loan_id):
    # Generate unique loan_id (LNXXXX)
    unique_loan_id = generate_loan_id()
    # Update loan status and set loan_id
    resp = supabase.table("loans").update({"status": "approved", "loan_id": unique_loan_id}).eq("id", loan_id).execute()
    if not resp.data:
        return jsonify({"status": "error", "message": "Loan not found or update failed"}), 404
    # Mark sureties as active for this loan
    supabase.table("sureties").update({"active": True}).eq("loan_id", loan_id).execute()
    # Create loan record
    supabase.table("loan_records").insert({
        "loan_id": unique_loan_id,
        "outstanding_balance": resp.data[0]["loan_amount"],
        "status": "active"
    }).execute()
    # Send mail to user
    member = get_member_by_customer_id(resp.data[0]["customer_id"])
    if member and member.get("name"):
        member_email_resp = supabase.table("members").select("email").eq("customer_id", resp.data[0]["customer_id"]).execute()
        if member_email_resp.data and member_email_resp.data[0].get("email"):
            send_loan_status_email(member_email_resp.data[0]["email"], member["name"], unique_loan_id, "approved")
    return jsonify({"status": "success", "loan_id": unique_loan_id}), 200

@finance_bp.route('/reject/<loan_id>', methods=['POST'])
def reject_loan(loan_id):
    reason = request.json.get("reason")
    if not reason:
        return jsonify({"status": "error", "message": "Rejection reason required"}), 400
    resp = supabase.table("loans").update({"status": "rejected", "rejection_reason": reason}).eq("id", loan_id).execute()
    if not resp.data:
        return jsonify({"status": "error", "message": "Loan not found or update failed"}), 404
    # Mark sureties as inactive for this loan
    supabase.table("sureties").update({"active": False}).eq("loan_id", loan_id).execute()
    # Send mail to user
    member = get_member_by_customer_id(resp.data[0]["customer_id"])
    if member and member.get("name"):
        member_email_resp = supabase.table("members").select("email").eq("customer_id", resp.data[0]["customer_id"]).execute()
        if member_email_resp.data and member_email_resp.data[0].get("email"):
            send_loan_status_email(member_email_resp.data[0]["email"], member["name"], loan_id, "rejected")
    return jsonify({"status": "success"}), 200

@finance_bp.route('/surety/check', methods=['POST'])
def check_surety_available():
    data = request.get_json(silent=True) or {}
    customer_id = data.get("customer_id")
    if not customer_id:
        return jsonify({"available": False, "reason": "Missing customer_id"}), 400

    # Check if member exists
    member_resp = supabase.table("members").select("customer_id").eq("customer_id", customer_id).execute()
    if not member_resp.data or len(member_resp.data) == 0:
        return jsonify({"available": False, "reason": "Customer not found"}), 200

    # Count active sureties (active loans)
    surety_resp = supabase.table("sureties").select("id").eq("surety_customer_id", customer_id).eq("active", True).execute()
    active_count = len(surety_resp.data) if surety_resp.data else 0

    if active_count >= 2:
        return jsonify({"available": False, "reason": "Customer is already a surety for 2 active loans"}), 200

    return jsonify({"available": True}), 200

@finance_bp.route('/certificate/<loan_id>')
def loan_certificate(loan_id):
    """
    View, print, or download a loan certificate by loan_id.
    Query param: action=view|download|print|json (default: view)
    """
    action = request.args.get('action', 'view')
    # Fetch loan
    loan_resp = supabase.table("loans").select("*").eq("loan_id", loan_id).execute()
    if not loan_resp.data:
        return jsonify({"status": "error", "message": "Loan not found"}), 404
    loan = loan_resp.data[0]

    # Fetch member with more detail (ensuring name is included)
    member_resp = supabase.table("members").select("*").eq("customer_id", loan["customer_id"]).execute()
    
    # Debug what we're getting from the database
    print(f"Member data for customer_id {loan['customer_id']}: {member_resp.data}")
    
    # Handle the case where member data is missing
    if not member_resp.data:
        member = {"name": "Customer information not available"}
    else:
        member = member_resp.data[0]
        # If name is still missing, set a fallback
        if not member.get("name"):
            member["name"] = "Name not found"

    # Fetch staff - return phone and name
    staff_resp = supabase.table("staff").select("name,phone").eq("email", loan["staff_email"]).execute()
    staff = staff_resp.data[0] if staff_resp.data else {}

    # Define society info variables
    society_name = "KSTHST Coof Society"
    taluk_name = "Taluk"
    district_name = "District"

    # Prepare data for template with explicit name mapping
    template_data = dict(
        loan=loan,
        member=member,
        member_name=member.get("name", "Name not available"),  # Explicitly map name
        staff=staff,
        society_name=society_name,
        taluk_name=taluk_name,
        district_name=district_name,
        amount_words=amount_to_words(loan["loan_amount"])
    )

    if action == "json":
        # Return all details as JSON
        return jsonify({
            "status": "success",
            "loan": loan,
            "member": member,
            "staff": staff,
            "society_name": society_name,
            "taluk_name": taluk_name,
            "district_name": district_name,
            "amount_words": template_data["amount_words"]
        }), 200

    html = render_template("loan_certificate.html", **template_data)

    if action == "download":
        pdf = pdfkit.from_string(html, False, options={'enable-local-file-access': None})
        response = make_response(pdf)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename={loan_id}.pdf'
        return response
    elif action == "print":
        html += "<script>window.onload = function(){window.print();}</script>"
        return html
    else:
        return html

@finance_bp.route('/check-surety', methods=['GET'])
def check_surety_get():
    # Now only retrieve customer_id parameter
    customer_id = request.args.get('customer_id')
    if not customer_id:
        return jsonify({"available": False, "reason": "Missing customer_id"}), 400

    member_resp = supabase.table("members") \
        .select("customer_id,name,phone") \
        .eq("customer_id", customer_id) \
        .execute()
    if not member_resp.data:
        return jsonify({"available": False, "reason": "Customer not found"}), 200

    member = member_resp.data[0]
    surety_resp = supabase.table("sureties") \
        .select("id") \
        .eq("surety_customer_id", customer_id) \
        .eq("active", True) \
        .execute()
    active_count = len(surety_resp.data or [])

    return jsonify({
        "available": active_count < 2,
        "member": {"customer_id": member["customer_id"], "name": member["name"], "phone": member["phone"]},
        "active_loan_count": active_count
    }), 200

@finance_bp.route('/surety/<customer_id>', methods=['GET'])
def surety_info(customer_id):
    """
    Fetch surety details by customer_id: name, phone, signature_url, photo_url, and active loan count.
    """
    member = get_member_by_customer_id(customer_id)
    if not member:
        return jsonify({"status": "error", "message": "Surety not found"}), 404
    # Count active loans backed as surety
    active_loans = supabase.table("sureties").select("id").eq("surety_customer_id", customer_id).eq("active", True).execute()
    return jsonify({
        "status": "success",
        "member": {
            "customer_id": member.get("customer_id"),
            "name": member.get("name"),
            "phone": member.get("phone"),
            "signature_url": member.get("signature_url"),
            "photo_url": member.get("photo_url")
        },
        "active_loan_count": len(active_loans.data)
    }), 200

@finance_bp.route('/fetch-account', methods=['GET'])
def fetch_account():
    """
    Fetch member details by customer_id.
    Returns: {name, phone, customer_id, photo_url, signature_url, kgid}
    """
    customer_id = request.args.get('customer_id')
    if not customer_id:
        return jsonify({"status": "error", "message": "Missing customer_id"}), 400
    member = supabase.table("members").select("name,phone,customer_id,photo_url,signature_url,kgid").eq("customer_id", customer_id).execute()
    if not member.data:
        return jsonify({"status": "error", "message": "Account not found"}), 404
    m = member.data[0]
    return jsonify({
        "status": "success",
        "name": m.get("name"),
        "phone": m.get("phone"),
        "customer_id": m.get("customer_id"),
        "photo_url": m.get("photo_url"),
        "signature_url": m.get("signature_url"),
        "kgid": m.get("kgid")
    }), 200