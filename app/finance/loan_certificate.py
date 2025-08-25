from flask import Blueprint, render_template, request, abort, make_response,jsonify
from supabase import create_client
import os
import inflect
import pdfkit
from datetime import datetime

loan_cert_bp = Blueprint('loan_cert', __name__)

# Helper for amount in words
p = inflect.engine()

def amount_to_words(amount):
    try:
        n = int(float(amount))
        words = p.number_to_words(n, andword='').replace(',', '')
        return words.title() + " Rupees Only"
    except Exception:
        return str(amount)

@loan_cert_bp.route('/loan/certificate/<loan_id>')
def loan_certificate(loan_id):
    action = request.args.get('action', 'view')
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Fetch loan by loan_id (LNxxxx) or UUID
    loan_resp = supabase.table("loans").select("*").eq("loan_id", loan_id).execute()
    loan = None
    if loan_resp.data:
        loan = loan_resp.data[0]
    else:
        # Try by UUID
        loan_resp2 = supabase.table("loans").select("*").eq("id", loan_id).execute()
        if loan_resp2.data:
            loan = loan_resp2.data[0]
    if not loan:
        return jsonify({"status": "error", "message": "Loan not found"}), 404

    # Fetch customer (all fields for template)
    member_resp = supabase.table("members").select("*").eq("customer_id", loan["customer_id"]).execute()
    member = member_resp.data[0] if member_resp.data else {}

    # Fetch staff
    staff_resp = supabase.table("staff").select("name,photo_url,signature_url").eq("email", loan["staff_email"]).execute()
    staff = staff_resp.data[0] if staff_resp.data else {}

    # Fetch sureties for this loan (by loan UUID) with correct columns
    sureties_resp = supabase.table("sureties").select("surety_name,surety_customer_id,surety_mobile,surety_signature_url,surety_photo_url,active").eq("loan_id", loan["id"]).execute()
    sureties = sureties_resp.data if sureties_resp.data else []
    loan["sureties"] = sureties

    # Society info
    society_name = os.environ.get("SOCIETY_NAME", "Kushtagi Taluk High School Employees Cooperative Society Ltd., Kushtagi-583277")
    taluk_name = os.environ.get("TALUK_NAME", "Kushtagi")
    district_name = os.environ.get("DISTRICT_NAME", "koppala")

    # Render HTML
    html = render_template(
        "loan_certificate.html",
        loan=loan,
        member=member,
        staff=staff,
        society_name=society_name,
        taluk_name=taluk_name,
        district_name=district_name,
        amount_words=amount_to_words(loan["loan_amount"])
    )

    if action == "download":
        pdf = pdfkit.from_string(html, False, options={'enable-local-file-access': None})
        response = make_response(pdf)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename={loan_id}.pdf'
        return response
    elif action == "print":
        # Add JS for print
        html += "<script>window.onload = function(){window.print();}</script>"
        return html
    else:
        return html

def register_certificate_routes(blueprint):
    pass  # This function is now removed. Only use /loan/certificate/<loan_id>
