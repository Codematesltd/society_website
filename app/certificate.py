from flask import Blueprint, render_template, abort, make_response
from flask import current_app
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

    # 4. Fetch staff signature and name by staff_id (if available)
    staff_name = None
    staff_signature_url = None
    staff_id = transaction.get("staff_id")
    if staff_id:
        staff_resp = supabase.table("staff").select("name,signature_url").eq("id", staff_id).execute()
        if staff_resp.data:
            staff_name = staff_resp.data[0].get("name")
            staff_signature_url = staff_resp.data[0].get("signature_url")

    # 5. Society info (customize as needed)
    society_name = current_app.config.get(
        "SOCIETY_NAME", "Kushtagi Taluk High School Employees Cooperative Society Ltd., Kushtagi-583277"
    )
    taluk_name = current_app.config.get("TALUK_NAME", "Kushtagi")
    district_name = current_app.config.get("DISTRICT_NAME", "koppala")

    # 6. Render HTML template with all required data
    html = render_template(
        "certificate.html",
        transaction=transaction,
        member=member,
        staff_signature_url=staff_signature_url,
        staff_name=staff_name,
        society_name=society_name,
        taluk_name=taluk_name,
        district_name=district_name,
        amount_words=amount_to_words(transaction["amount"])
    )

    # 7. Generate PDF from HTML using pdfkit
    #    - Ensure wkhtmltopdf is installed and available in PATH
    #    - For Render.com, see apt-get command below
    pdf = pdfkit.from_string(html, False, options={
        'enable-local-file-access': None  # Allow loading local/static files
    })

    # 8. Return PDF as HTTP response with correct headers
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename={stid}.pdf'
    return response

# Example apt-get command for Render.com build process:
# apt-get update && apt-get install -y wkhtmltopdf
    