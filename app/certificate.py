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
        # Use Indian numbering system for lakhs/crores
        def indian_number_words(num):
            if num < 100000:
                return p.number_to_words(num, andword='').replace(',', '')
            elif num < 10000000:
                lakhs = num // 100000
                rem = num % 100000
                lakhs_part = p.number_to_words(lakhs, andword='').replace(',', '') + " Lakh"
                if rem:
                    rem_part = p.number_to_words(rem, andword='').replace(',', '')
                    return lakhs_part + " " + rem_part
                return lakhs_part
            else:
                crores = num // 10000000
                rem = num % 10000000
                crores_part = p.number_to_words(crores, andword='').replace(',', '') + " Crore"
                if rem:
                    lakhs = rem // 100000
                    rem2 = rem % 100000
                    lakhs_part = ""
                    if lakhs:
                        lakhs_part = " " + p.number_to_words(lakhs, andword='').replace(',', '') + " Lakh"
                    if rem2:
                        rem_part = " " + p.number_to_words(rem2, andword='').replace(',', '')
                    else:
                        rem_part = ""
                    return crores_part + lakhs_part + rem_part
                return crores_part
        words = indian_number_words(n)
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

    # 4. Society info
    society_name = os.environ.get("SOCIETY_NAME", "Kushtagi Taluk High School Employees Cooperative Society Ltd., Kushtagi-583277")
    taluk_name = os.environ.get("TALUK_NAME", "Kushtagi")
    district_name = os.environ.get("DISTRICT_NAME", "koppala")

    # 6. Prepare template data (no staff fields)
    template_data = dict(
        transaction=transaction,
        member=member,
        society_name=society_name,
        taluk_name=taluk_name,
        district_name=district_name,
        amount_words=amount_to_words(transaction["amount"]),
        society_logo_url="https://geqletipzwxokceydhmi.supabase.co/storage/v1/object/public/staff-add/society_logo.png"
    )

    # 7. Handle action param
    action = request.args.get("action", "view")
    if action == "json":
        return jsonify({
            "status": "success",
            "transaction": transaction,
            "member": member,
            "society_name": society_name,
            "taluk_name": taluk_name,
            "district_name": district_name,
            "amount_words": template_data["amount_words"]
        }), 200

    html = render_template("certificate.html", **template_data)

    if action == "download":
        from xhtml2pdf import pisa
        pdf = BytesIO()
        pisa.CreatePDF(html, dest=pdf, encoding='utf-8')
        response = make_response(pdf.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename={stid}.pdf'
        return response
    elif action == "print":
        html += "<script>window.onload = function(){window.print();}</script>"
        return html
    else:  # view
        return html

@certificate_bp.route('/fd/certificate/<fdid>')
def fd_certificate(fdid):
    """
    Fixed Deposit certificate (view / download / print / json)
    URL used in approval email: /fd/certificate/<fdid>?action=view
    """
    action = request.args.get('action', 'view')

    # Supabase client
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Fetch FD by textual fdid or internal id
    fd_resp = supabase.table("fixed_deposits").select("*").eq("fdid", fdid).limit(1).execute()
    fd = None
    if fd_resp.data:
        fd = fd_resp.data[0]
    else:
        # fallback by id (UUID)
        fd_resp2 = supabase.table("fixed_deposits").select("*").eq("id", fdid).limit(1).execute()
        if fd_resp2.data:
            fd = fd_resp2.data[0]
    if not fd:
        return jsonify({'status': 'error', 'message': 'FD not found'}), 404

    # Member
    member_resp = supabase.table("members").select("customer_id,name,kgid,phone,email,photo_url").eq("customer_id", fd.get("customer_id")).limit(1).execute()
    member = member_resp.data[0] if member_resp.data else {}

    # Society info
    society_name = os.environ.get("SOCIETY_NAME", "Kushtagi Taluk High School Employees Cooperative Society Ltd., Kushtagi-583277")
    taluk_name = os.environ.get("TALUK_NAME", "Kushtagi")
    district_name = os.environ.get("DISTRICT_NAME", "koppala")

    # Compute interest & maturity (simple interest)
    try:
        principal = float(fd.get("amount") or 0)
        rate = float(fd.get("interest_rate") or 0)
        tenure_m = int(fd.get("tenure") or 0)
    except Exception:
        principal, rate, tenure_m = 0.0, 0.0, 0
    interest = round(principal * rate * tenure_m / (12 * 100), 2)
    maturity_amount = round(principal + interest, 2)

    # Maturity date
    maturity_date = None
    try:
        if fd.get("deposit_date"):
            from datetime import datetime as _dt
            d = _dt.strptime(fd["deposit_date"], "%Y-%m-%d")
            year = d.year + (d.month - 1 + tenure_m) // 12
            month = (d.month - 1 + tenure_m) % 12 + 1
            day = min(d.day, 28)
            maturity_date = f"{year:04d}-{month:02d}-{day:02d}"
    except Exception:
        maturity_date = None

    ctx = dict(
        fd=fd,
        member=member,
        principal=principal,
        rate=rate,
        tenure_months=tenure_m,
        interest=interest,
        maturity_amount=maturity_amount,
        maturity_date=maturity_date,
        amount_words=amount_to_words(maturity_amount),
        society_name=society_name,
        taluk_name=taluk_name,
        district_name=district_name
    )

    if action == 'json':
        return jsonify({'status': 'success', **ctx}), 200

    html = render_template("fd_certificate.html", **ctx)

    if action == 'download':
        resp = make_response(html)
        resp.headers['Content-Type'] = 'text/html; charset=utf-8'
        resp.headers['Content-Disposition'] = f'attachment; filename=fd_{fdid}.html'
        return resp
    if action == 'print':
        html += "<script>window.onload=function(){window.print();}</script>"
        return html
    return html

