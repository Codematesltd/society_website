from flask import request, jsonify, render_template, make_response, abort
import os
import uuid
import re
from supabase import create_client, Client
from dotenv import load_dotenv
import pdfkit
import inflect

from . import finance_bp

load_dotenv()
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
p = inflect.engine()

def generate_loan_id():
    """Generate a unique loan_id like LN0001."""
    resp = supabase.table("loans").select("loan_id").like("loan_id", "LN%").order("loan_id", desc=True).limit(1).execute()
    if resp.data and resp.data[0].get("loan_id"):
        last = resp.data[0]["loan_id"]
        match = re.match(r"LN(\d{4})", last)
        seq = int(match.group(1)) + 1 if match else 1
    else:
        seq = 1
    return f"LN{seq:04d}"

def get_member_by_customer_id(customer_id):
    resp = supabase.table("members").select("customer_id,name,phone,signature_url,photo_url").eq("customer_id", customer_id).execute()
    return resp.data[0] if resp.data else None

def get_staff_by_email(email):
    """Fetch staff record by email."""
    resp = supabase.table("staff").select("email,name,photo_url,signature_url").eq("email", email).execute()
    return resp.data[0] if resp.data else None

def amount_to_words(amount):
    try:
        n = int(float(amount))
        words = p.number_to_words(n, andword='').replace(',', '')
        return words.title() + " Rupees Only"
    except Exception:
        return str(amount)

@finance_bp.route('/apply', methods=['POST'])
def apply_loan():
    data = request.json
    loan_type = data.get("loan_type")
    customer_id = data.get("customer_id")
    loan_amount = data.get("loan_amount")
    interest_rate = data.get("interest_rate")
    loan_term_months = data.get("loan_term_months")
    purpose = data.get("purpose_of_loan") or data.get("purpose_of_emergency_loan")
    sureties = data.get("sureties", [])

    # --- Staff details from session ---
    from flask import session
    staff_email = session.get("staff_email")
    if not staff_email:
        return jsonify({"status": "error", "message": "Staff not logged in"}), 401
    staff = get_staff_by_email(staff_email)
    if not staff:
        return jsonify({"status": "error", "message": "Staff not found"}), 404

    # Validation
    if loan_type not in ["normal", "emergency"]:
        return jsonify({"status": "error", "message": "Invalid loan type"}), 400
    if not customer_id or not loan_amount or not interest_rate or not loan_term_months or not purpose:
        return jsonify({"status": "error", "message": "Missing required fields"}), 400
    if not isinstance(sureties, list) or not (1 <= len(sureties) <= 2):
        return jsonify({"status": "error", "message": "Must provide 1 or 2 sureties"}), 400

    # Surety validation
    surety_ids = set()
    surety_objs = []
    for s_id in sureties:
        if s_id == customer_id:
            return jsonify({"status": "error", "message": "Applicant cannot be their own surety"}), 400
        if s_id in surety_ids:
            return jsonify({"status": "error", "message": "Duplicate surety for same loan"}), 400
        # Check surety active loan count
        active = supabase.table("sureties").select("id").eq("surety_customer_id", s_id).eq("active", True).execute()
        if active.data and len(active.data) >= 2:
            return jsonify({"status": "error", "message": f"Surety {s_id} already has 2 active loans"}), 400
        member = get_member_by_customer_id(s_id)
        if not member:
            return jsonify({"status": "error", "message": f"Surety {s_id} not found"}), 404
        surety_objs.append({
            "surety_customer_id": member["customer_id"],
            "surety_name": member["name"],
            "surety_mobile": member["phone"],
            "surety_signature_url": member["signature_url"],
            "surety_photo_url": member["photo_url"]
        })
        surety_ids.add(s_id)

    # Insert loan (pending) with staff details
    loan_data = {
        "customer_id": customer_id,
        "loan_type": loan_type,
        "loan_amount": loan_amount,
        "interest_rate": interest_rate,
        "loan_term_months": loan_term_months,
        "purpose_of_loan": purpose if loan_type == "normal" else None,
        "purpose_of_emergency_loan": purpose if loan_type == "emergency" else None,
        "status": "pending",
        "staff_email": staff["email"],
        "staff_name": staff["name"],
        "staff_photo_url": staff["photo_url"],
        "staff_signature_url": staff["signature_url"]
    }
    loan_resp = supabase.table("loans").insert(loan_data).execute()
    if not loan_resp.data:
        return jsonify({"status": "error", "message": "Failed to create loan"}), 500
    loan_id = loan_resp.data[0]["id"]

    # Insert sureties
    for s in surety_objs:
        s["loan_id"] = loan_id
        s["active"] = True
        supabase.table("sureties").insert(s).execute()

    return jsonify({"status": "success", "loan_id": loan_id}), 201

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
        "photo_url": loan_data.get("staff_photo_url"),
        "signature_url": loan_data.get("staff_signature_url")
    }
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

    # Fetch member
    member_resp = supabase.table("members").select("name,photo_url").eq("customer_id", loan["customer_id"]).execute()
    member = member_resp.data[0] if member_resp.data else {}

    # Fetch staff
    staff_resp = supabase.table("staff").select("name,photo_url,signature_url").eq("email", loan["staff_email"]).execute()
    staff = staff_resp.data[0] if staff_resp.data else {}

    # Fix staff signature URL if it's a local file (not a full URL)
    if staff and staff.get("signature_url") and not staff["signature_url"].startswith("http"):
        from flask import url_for
        staff["signature_url"] = url_for('static', filename=staff["signature_url"], _external=True)

    # Society info
    society_name = os.environ.get("SOCIETY_NAME", "Kushtagi Taluk High School Employees Cooperative Society Ltd., Kushtagi-583277")
    taluk_name = os.environ.get("TALUK_NAME", "Kushtagi")
    district_name = os.environ.get("DISTRICT_NAME", "koppala")

    # Prepare data for template
    template_data = dict(
        loan=loan,
        member=member,
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

