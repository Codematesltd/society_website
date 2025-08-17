from flask import Blueprint, render_template, abort, make_response, request, jsonify, current_app, session
from io import BytesIO
from supabase import create_client
import os
import inflect
import pdfkit  # Use pdfkit for PDF generation

certificate_bp = Blueprint('certificate', __name__)

# Helper for amount in words
p = inflect.engine()

def amount_to_words(amount):
    try:
        n = int(float(amount))
        words = p.number_to_words(n, andword='').replace(',', '')
        return words.title() + " Rupees Only"
    except Exception:
        return str(amount)

def get_staff_by_email(email, supabase_client):
    if not email:
        return None
    resp = supabase_client.table("staff").select("email,name,photo_url,signature_url").eq("email", email).execute()
    return resp.data[0] if resp.data else None

@certificate_bp.route('/certificate/<stid>')
def certificate_pdf(stid):
    # 1. Setup Supabase client
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    # 2. Fetch transaction by STID
    tx_resp = supabase.table("transactions").select("*").eq("stid", stid).execute()
    if not tx_resp.data:
        abort(404, "Transaction not found")
    transaction = tx_resp.data[0]

    # 3. Fetch member by customer_id
    member_resp = supabase.table("members").select("*").eq("customer_id", transaction["customer_id"]).execute()
    member = member_resp.data[0] if member_resp.data else {}

    # 4. Fetch staff from session
    staff_email = session.get("staff_email")
    staff = get_staff_by_email(staff_email, supabase)

    # 5. Society info
    society_name = os.environ.get("SOCIETY_NAME", "Kushtagi Taluk High School Employees Cooperative Society Ltd., Kushtagi-583277")
    taluk_name = os.environ.get("TALUK_NAME", "Kushtagi")
    district_name = os.environ.get("DISTRICT_NAME", "koppala")

    # 6. Prepare template data
    template_data = dict(
        transaction=transaction,
        member=member,
        staff=staff,
        staff_signature_url=staff.get("signature_url") if staff else None,
        staff_name=staff.get("name") if staff else None,
        society_name=society_name,
        taluk_name=taluk_name,
        district_name=district_name,
        amount_words=amount_to_words(transaction["amount"])
    )

    # 7. Handle action param
    action = request.args.get("action", "view")
    if action == "json":
        return jsonify({
            "status": "success",
            "transaction": transaction,
            "member": member,
            "staff": staff,
            "society_name": society_name,
            "taluk_name": taluk_name,
            "district_name": district_name,
            "amount_words": template_data["amount_words"]
        }), 200

    html = render_template("certificate.html", **template_data)

    if action == "download":
        pdf = pdfkit.from_string(html, False, options={'enable-local-file-access': None})
        response = make_response(pdf)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename={stid}.pdf'
        return response
    elif action == "print":
        html += "<script>window.onload = function(){window.print();}</script>"
        return html
    else:  # view
        return html

# Example apt-get command for Render.com build process:
# apt-get update && apt-get install -y wkhtmltopdf
# Example apt-get command for Render.com build process:
# apt-get update && apt-get install -y wkhtmltopdf
