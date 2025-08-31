# Route to render loan_repayment.html for staff dashboard iframe

from flask import request, jsonify, render_template, make_response, abort, session, url_for, current_app
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
import pdfkit
import smtplib
from email.mime.application import MIMEApplication

# Import notify_admin_loan_application to fix NameError
from app.auth.routes import notify_admin_loan_application

# Use the shared finance blueprint defined in app.finance.__init__
from . import finance_bp

# Route to view/print/download a loan repayment certificate
@finance_bp.route('/repayment-certificate/<repayment_id>')
def repayment_certificate(repayment_id):
    """
    View, print, or download a loan repayment certificate by repayment record ID.
    Query param: action=view|download|print|json (default: view)
    """
    action = request.args.get('action', 'view')
    # Fetch repayment record
    repayment = supabase.table("loan_records").select("*", "loan_id").eq("id", repayment_id).execute()
    if not repayment.data:
        return jsonify({"status": "error", "message": "Repayment record not found"}), 404
    repayment_row = repayment.data[0]

    # Fetch loan details
    loan = None
    loan_id = repayment_row.get("loan_id")
    if loan_id:
        loan_resp = supabase.table("loans").select("*", "customer_id").eq("loan_id", loan_id).execute()
        if loan_resp.data:
            loan = loan_resp.data[0]
    if not loan:
        return jsonify({"status": "error", "message": "Loan not found for repayment"}), 404

    # Fetch member details
    member = None
    customer_id = loan.get("customer_id")
    if customer_id:
        member_resp = supabase.table("members").select("*").eq("customer_id", customer_id).execute()
        if member_resp.data:
            member = member_resp.data[0]
    if not member:
        member = {"name": "Customer information not available"}

    # Ensure repayment values are always present and correct
    repayment_amount = repayment_row.get("repayment_amount")
    try:
        repayment_amount = float(repayment_amount) if repayment_amount not in (None, '', 'None') else 0.0
    except Exception:
        repayment_amount = 0.0

    interest_paid = repayment_row.get("interest_amount")
    try:
        interest_paid = float(interest_paid) if interest_paid not in (None, '', 'None') else 0.0
    except Exception:
        interest_paid = 0.0

    # If principal_amount is missing, calculate as repayment_amount - interest_paid
    principal_paid = repayment_row.get("principal_amount")
    if principal_paid in (None, '', 'None', '-'): 
        principal_paid = repayment_amount - interest_paid
    try:
        principal_paid = float(principal_paid)
    except Exception:
        principal_paid = 0.0

    # Date fallback
    repayment_date = repayment_row.get("repayment_date")
    if not repayment_date or repayment_date in (None, '', 'None'):
        repayment_date = datetime.now().strftime("%Y-%m-%d")

    # Amount in words fallback
    amount_words = amount_to_words(repayment_amount) if repayment_amount else "Zero Rupees Only"

    cert_data = dict(
        transaction={
            "stid": repayment_row.get("id"),
            "date": repayment_date,
            "amount": repayment_amount,
            "principal_paid": principal_paid,
            "interest_paid": interest_paid,
            "from_account": member.get("customer_id", ""),
            "to_account": loan.get("loan_id", ""),
            "balance_after": repayment_row.get("outstanding_balance", 0.0),
            "remarks": repayment_row.get("remarks", f"Loan repayment for {loan.get('loan_id')}")
        },
        member=member,
        society_name="KSTHST Coof Society",
        taluk_name="Taluk",
        district_name="District",
        amount_words=amount_words
    )

    if action == "json":
        return jsonify({"status": "success", **cert_data}), 200

    html = render_template("repayment_certificate.html", **cert_data)

    if action == "download":
        # Return HTML attachment instead of PDF (no wkhtmltopdf dependency)
        response = make_response(html)
        response.headers['Content-Type'] = 'text/html; charset=utf-8'
        response.headers['Content-Disposition'] = f'attachment; filename=repayment_{repayment_id}.html'
        return response
    elif action == "print":
        html += "<script>window.onload = function(){window.print();}</script>"
        return html
    else:
        return html
# Route to render loan_repayment.html for staff dashboard iframe

from flask import request, jsonify, render_template, make_response, abort, session, url_for, current_app
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
import pdfkit
import smtplib
from email.mime.application import MIMEApplication

# Import notify_admin_loan_application to fix NameError
from app.auth.routes import notify_admin_loan_application

# Use the shared finance blueprint defined in app.finance.__init__
from . import finance_bp

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
    base_url = os.environ.get('BASE_URL', 'https://ksthstsociety.com')
    cert_url = f"{base_url}/loan/certificate/{loan_id}?action=view"
    if status == "pending":
        subject = f"Your Loan Application Has Been Received – Reference: {loan_id}"
        body = (
            f"Dear {name},\n\n"
            f"Thank you for choosing KSTHST Coof Society.\n\n"
            f"We have received your loan application (Reference ID: {loan_id}) and it is now under review.\n\n"
            f"You can track the status or view the application certificate here:\n{cert_url}\n\n"
            f"If you have any questions, reply to this email or contact support.\n\n"
            f"Best regards,\n"
            f"KSTHST Coof Society Team"
        )
    elif status == "approved":
        subject = f"Congratulations! Your Loan Application (ID: {loan_id}) is Approved"
        body = (
            f"Dear {name},\n\n"
            f"Congratulations! Your loan application (Reference ID: {loan_id}) has been approved.\n\n"
            f"You may view and download your official loan certificate here:\n{cert_url}\n\n"
            f"If you need assistance, reply to this email.\n\n"
            f"Best regards,\n"
            f"KSTHST Coof Society Team"
        )
    elif status == "rejected":
        subject = f"Update on Your Loan Application (ID: {loan_id})"
        body = (
            f"Dear {name},\n\n"
            f"We regret to inform you that your loan application (Reference ID: {loan_id}) was not approved at this time.\n\n"
            f"For clarification or to reapply in the future, please contact our support team.\n\n"
            f"Best regards,\n"
            f"KSTHST Coof Society Team"
        )
    else:
        subject = f"Update Regarding Your Loan Application (ID: {loan_id})"
        body = (
            f"Dear {name},\n\n"
            f"There is an update regarding your loan application (Reference ID: {loan_id}).\n"
            f"Current status: {status}\n\n"
            f"For more details, log in to your account or contact support.\n\n"
            f"Best regards,\n"
            f"KSTHST Coof Society Team"
        )
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

def _auto_complete_loan_if_fully_repaid(loan_row, total_repaid):
    """
    If outstanding <= 0 and loan is approved, mark it completed.
    Returns possibly updated loan_row (status field adjusted in-memory too).
    """
    try:
        loan_amount = float(loan_row.get("loan_amount", 0) or 0)
        outstanding = loan_amount - total_repaid
        if outstanding <= 0 and loan_row.get("status") == "approved":
            # Update DB status to completed
            supabase.table("loans").update({"status": "completed"}).eq("id", loan_row["id"]).execute()
            loan_row["status"] = "completed"
    except Exception as e:
        print(f"Auto-complete check failed for loan {loan_row.get('id')}: {e}")
    return loan_row

@finance_bp.route('/apply', methods=['POST'])
@finance_bp.route('/loan/apply', methods=['POST'])   # alias for staff_dashboard.js
def apply_loan():
    """
    Create a new loan application (status: pending_approval).
    Expects JSON:
      loan_type, customer_id, loan_amount, interest_rate, loan_term_months, sureties[]
      purpose_of_loan (normal) OR purpose_of_emergency_loan (emergency)
    Returns: {status, message, loan_id (UUID), certificate_url (None until approval)}
    """
    try:
        data = request.get_json(silent=True) or {}
        required = ['loan_type', 'customer_id', 'loan_amount', 'interest_rate', 'loan_term_months']
        missing = [f for f in required if not data.get(f)]
        if missing:
            return jsonify({"status": "error", "message": f"Missing fields: {', '.join(missing)}"}), 400

        loan_type = data.get('loan_type')
        customer_id = data.get('customer_id')
        try:
            loan_amount = float(data.get('loan_amount'))
            interest_rate = float(data.get('interest_rate'))
            loan_term_months = int(data.get('loan_term_months'))
        except Exception:
            return jsonify({"status": "error", "message": "Invalid numeric field(s)."}), 400

        if loan_amount <= 0 or interest_rate < 0 or loan_term_months <= 0:
            return jsonify({"status": "error", "message": "Numeric fields out of range."}), 400

        # Purpose handling
        purpose_normal = data.get('purpose_of_loan')
        purpose_emergency = data.get('purpose_of_emergency_loan')
        purpose_field = {}
        if loan_type == 'normal' and purpose_normal:
            purpose_field['purpose_of_loan'] = purpose_normal
        if loan_type == 'emergency' and purpose_emergency:
            purpose_field['purpose_of_emergency_loan'] = purpose_emergency

        # Staff identity (session or header)
        staff_email = session.get('staff_email') or request.headers.get('X-Staff-Email')
        staff_name = None
        staff_phone = None
        if staff_email:
            try:
                sresp = supabase.table('staff').select('name,phone').eq('email', staff_email).limit(1).execute()
                if sresp.data:
                    staff_name = sresp.data[0].get('name')
                    staff_phone = sresp.data[0].get('phone')
            except Exception:
                pass

        loan_insert = {
            "customer_id": customer_id,
            "loan_type": loan_type,
            "loan_amount": loan_amount,
            "interest_rate": interest_rate,
            "loan_term_months": loan_term_months,
            "status": "pending_approval",
            "staff_email": staff_email,
            "staff_name": staff_name,
            "staff_phone": staff_phone,
            **purpose_field
        }

        ins_resp = supabase.table("loans").insert(loan_insert).execute()
        if not ins_resp.data:
            return jsonify({"status": "error", "message": "Failed to create loan"}), 500
        loan_row = ins_resp.data[0]
        loan_uuid = loan_row.get('id')


        # Generate LNxxxx and update loan row immediately
        unique_loan_id = generate_loan_id()
        supabase.table("loans").update({"loan_id": unique_loan_id}).eq("id", loan_uuid).execute()

        # Insert sureties (array of IDs passed) using loan UUID (loan_uuid)
        sureties = data.get('sureties') or []
        clean_sureties = []
        for s in sureties:
            sid = str(s).strip()
            if sid and len(clean_sureties) < 2:
                clean_sureties.append(sid)
        for s in clean_sureties:
            try:
                # Fetch surety member details for required fields
                surety_member = supabase.table("members").select("name,phone,signature_url,photo_url").eq("customer_id", s).limit(1).execute()
                if surety_member.data and len(surety_member.data) > 0:
                    sm = surety_member.data[0]
                    supabase.table("sureties").insert({
                        "loan_id": loan_uuid,          # use UUID for sureties linkage
                        "surety_customer_id": s,
                        "surety_name": sm.get("name", ""),
                        "surety_mobile": sm.get("phone", ""),
                        "surety_signature_url": sm.get("signature_url"),
                        "surety_photo_url": sm.get("photo_url"),
                        "active": False
                    }).execute()
                else:
                    # Insert with minimal info if member not found
                    supabase.table("sureties").insert({
                        "loan_id": loan_uuid,
                        "surety_customer_id": s,
                        "surety_name": "",
                        "surety_mobile": "",
                        "surety_signature_url": None,
                        "surety_photo_url": None,
                        "active": False
                    }).execute()
            except Exception:
                pass  # continue inserting others

        # Notify admins (use LNxxxx)
        try:
            notify_admin_loan_application(
                loan_id=unique_loan_id,
                customer_id=customer_id,
                loan_type=loan_type,
                amount=loan_amount
            )
        except Exception as e:
            print(f"[WARN] notify_admin_loan_application failed: {e}")

        # Member confirmation email
        try:
            member_email_resp = supabase.table("members").select("email,name").eq("customer_id", customer_id).limit(1).execute()
            if member_email_resp.data and member_email_resp.data[0].get("email"):
                send_loan_status_email(
                    member_email_resp.data[0]["email"],
                    member_email_resp.data[0].get("name") or "Member",
                    unique_loan_id,
                    "pending"
                )
        except Exception as e:
            print(f"[WARN] member email send failed: {e}")

        return jsonify({
            "status": "success",
            "message": "Loan application submitted and pending approval",
            "loan_id": unique_loan_id,
            "certificate_url": None
        }), 200
    except Exception as e:
        import traceback
        print("Error in apply_loan:", e)
        print(traceback.format_exc())
        return jsonify({"status": "error", "message": str(e)}), 500


@finance_bp.route('/<loan_id>', methods=['GET'])
def get_loan(loan_id):
    """
    Fetch loan details by either UUID (id) or textual loan_id (LNxxxx).
    """
    # Try to fetch by UUID first, but only if it looks like a UUID
    import re
    uuid_regex = re.compile(r"^[0-9a-fA-F-]{32,36}$")
    loan = None

    if uuid_regex.match(loan_id):
        loan_resp = supabase.table("loans").select("*").eq("id", loan_id).execute()
        if loan_resp.data:
            loan = loan_resp.data[0]
    if not loan:
        # Try by textual loan_id (e.g. LN0002)
        loan_resp = supabase.table("loans").select("*").eq("loan_id", loan_id).execute()
        if loan_resp.data:
            loan = loan_resp.data[0]
    if not loan:
        return jsonify({"status": "error", "message": "Loan not found"}), 404

    loan_data = loan
    # Fetch customer details
    customer = supabase.table("members").select("customer_id,name,phone,photo_url,signature_url").eq("customer_id", loan_data["customer_id"]).execute()
    # Fetch sureties for this loan by UUID only (since sureties.loan_id is uuid)
    surety_filters = []
    if loan_data.get('id'):
        surety_filters.append(f"loan_id.eq.{loan_data['id']}")
    if surety_filters:
        sureties = supabase.table("sureties").select("*").or_(','.join(surety_filters)).execute()
    else:
        sureties = type('obj', (object,), {'data': []})()  # empty result
    # Fetch repayment records for both textual loan_id and UUID
    loan_id_text = loan_data.get("loan_id")
    rec_resp1 = supabase.table("loan_records").select("*").eq("loan_id", loan_id_text).execute() if loan_id_text else None
    rec_resp2 = supabase.table("loan_records").select("*").eq("loan_id", loan_data["id"]).execute()
    seen = set()
    all_records = []
    for r in (rec_resp1.data if rec_resp1 and rec_resp1.data else []) + (rec_resp2.data or []):
        if r["id"] not in seen:
            all_records.append(r)
            seen.add(r["id"])
    # Sort by repayment_date (oldest first, nulls last)

    records = sorted(all_records, key=lambda r: (r["repayment_date"] or "9999-12-31"))

    # --- Interest calculation for each repayment record ---
    interest_rate = float(loan_data.get("interest_rate", 0))
    prev_date = None
    prev_balance = float(loan_data.get("loan_amount", 0))
    for rec in records:
        # Calculate days since last payment
        curr_date = rec.get("repayment_date")
        if curr_date and prev_date:
            days = (datetime.strptime(curr_date, "%Y-%m-%d") - datetime.strptime(prev_date, "%Y-%m-%d")).days
        elif curr_date:
            # First payment: since loan start (assume created_at or repayment_date)
            loan_start = loan_data.get("created_at")
            if loan_start:
                loan_start_date = loan_start.split("T")[0]
                days = (datetime.strptime(curr_date, "%Y-%m-%d") - datetime.strptime(loan_start_date, "%Y-%m-%d")).days
            else:
                days = 0
        else:
            days = 0

        # Calculate interest for this period
        if days > 0 and interest_rate > 0:
            interest = prev_balance * (interest_rate / 100) * (days / 365)
        else:
            interest = 0.0
        rec["calculated_interest"] = round(interest, 2)
        prev_date = curr_date
        prev_balance = float(rec.get("outstanding_balance", prev_balance))

    # NEW: compute total repaid & auto-complete
    try:
        total_repaid = sum(float(r.get("repayment_amount") or 0) for r in records)
        _auto_complete_loan_if_fully_repaid(loan_data, total_repaid)
    except Exception as e:
        print(f"Failed computing repayment summary for loan {loan_id}: {e}")

    staff_details = {
        "email": loan_data.get("staff_email"),
        "name": loan_data.get("staff_name"),
        "phone": loan_data.get("staff_phone")
    }
    return jsonify(
        status="success",
        loan=loan_data,
        customer=customer.data[0] if customer.data else {},
        sureties=sureties.data,
        records=records,
        staff=staff_details
    ), 200

@finance_bp.route('/approve/<loan_id>', methods=['POST'])
def approve_loan(loan_id):
    # Only update status, do not generate a new LNxxxx loan_id
    # Fetch the loan to get the existing LNxxxx
    loan_resp = supabase.table("loans").select("loan_id,loan_amount,interest_rate,loan_term_months,customer_id").eq("id", loan_id).execute()
    if not loan_resp.data:
        return jsonify({"status": "error", "message": "Loan not found or update failed"}), 404
    loan_row = loan_resp.data[0]
    ln_loan_id = loan_row["loan_id"]
    # Update status only
    supabase.table("loans").update({"status": "approved"}).eq("id", loan_id).execute()
    # Mark sureties as active for this loan (do NOT update loan_id to LNxxxx, keep UUID linkage)
    supabase.table("sureties").update({"active": True}).eq("loan_id", loan_id).execute()
    # --- Calculate principal, interest, outstanding, and EMI ---
    principal = float(loan_row["loan_amount"])
    rate = float(loan_row["interest_rate"])
    months = int(loan_row["loan_term_months"])
    total_interest = round(principal * rate * months / (12 * 100), 2)
    outstanding = round(principal + total_interest, 2)
    monthly_rate = rate / (12 * 100)
    if monthly_rate > 0:
        emi = round(principal * monthly_rate * (1 + monthly_rate) ** months / ((1 + monthly_rate) ** months - 1), 2)
    else:
        emi = round(principal / months, 2) if months > 0 else principal
    # Store only a single summary row for the loan in loan_records
    supabase.table("loan_records").insert({
        "loan_id": ln_loan_id,
        "repayment_date": None,
        "repayment_amount": None,
        "outstanding_balance": outstanding,
        "status": "active",
        "interest_amount": total_interest
    }).execute()
    # Send mail to user
    member = get_member_by_customer_id(loan_row["customer_id"])
    if member and member.get("name"):
        member_email_resp = supabase.table("members").select("email").eq("customer_id", loan_row["customer_id"]).execute()
        if member_email_resp.data and member_email_resp.data[0].get("email"):
            send_loan_status_email(member_email_resp.data[0]["email"], member["name"], ln_loan_id, "approved")
    # Return JSON with download URL for frontend to trigger download
    from flask import url_for
    cert_url = url_for('finance.loan_certificate', loan_id=ln_loan_id, action='download', _external=True)
    return jsonify({"status": "success", "download_url": cert_url}), 200

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
    # Fetch loan by textual loan_id (LNxxxx) or UUID fallback
    loan_resp = supabase.table("loans").select("*").eq("loan_id", loan_id).execute()
    loan = loan_resp.data[0] if loan_resp.data else None
    if not loan:
        uuid_try = supabase.table("loans").select("*").eq("id", loan_id).execute()
        if uuid_try.data:
            loan = uuid_try.data[0]
    if not loan:
        return jsonify({"status": "error", "message": "Loan not found"}), 404

    # Fetch member with more detail (ensuring name is included)
    member_resp = supabase.table("members").select("*").eq("customer_id", loan["customer_id"]).execute()
    
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

    # Fetch sureties for this loan (sureties.loan_id links to loan UUID)
    try:
        sureties_resp = supabase.table("sureties").select("*").eq("loan_id", loan.get("id")).execute()
        loan["sureties"] = sureties_resp.data if sureties_resp.data else []
    except Exception:
        loan["sureties"] = []

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
        # Return HTML attachment instead of PDF (no wkhtmltopdf dependency)
        response = make_response(html)
        response.headers['Content-Type'] = 'text/html; charset=utf-8'
        response.headers['Content-Disposition'] = f'attachment; filename=loan_{loan_id}.html'
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

@finance_bp.route('/fetch_customer_details', methods=['GET'])
def fetch_customer_details():
    """
    Fetch comprehensive customer details including:
    - All member information (personal, contact, financial)
    - All loans (active, pending, approved, rejected)
    - Loan repayment records
    - Outstanding balances
    - Staff information who processed the loans
    - Sureties information
    """
    customer_id = request.args.get('customer_id')
    
    if not customer_id:
        return jsonify({"status": "error", "message": "Missing customer_id parameter"}), 400
    
    # Fetch comprehensive customer/member information
    customer_resp = supabase.table("members").select("*").eq("customer_id", customer_id).execute()

    if not customer_resp.data:
        return jsonify({
            "status": "error", 
            "message": f"Customer not found for ID: {customer_id}",
            "customer_id": customer_id
        }), 404

    customer_info = customer_resp.data[0]

    # Remove sensitive information from response
    sensitive_fields = ['password', 'otp', 'reset_token']
    for field in sensitive_fields:
        customer_info.pop(field, None)

    # Ensure salary is present (default to 0 if missing)
    if "salary" not in customer_info:
        customer_info["salary"] = 0

    # Map DB fields to API fields for Aadhaar and PAN
    customer_info["aadhaar_card"] = customer_info.get("aadhar_no", "")
    customer_info["pan_card"] = customer_info.get("pan_no", "")

    # Fetch all loans for the customer
    loans_resp = supabase.table("loans").select("*").eq("customer_id", customer_id).execute()

    loans_with_details = []

    if loans_resp.data:
        for loan in loans_resp.data:
            loan_details = dict(loan)  # Copy loan data

            # Fetch loan records (repayments) for this specific loan
            if loan.get("loan_id"):
                records_resp = supabase.table("loan_records").select("*").eq("loan_id", loan["loan_id"]).execute()
                loan_details["repayment_records"] = records_resp.data if records_resp.data else []

                # Calculate total repaid amount
                total_repaid = 0
                for record in loan_details["repayment_records"]:
                    if record.get("repayment_amount"):
                        total_repaid += float(record["repayment_amount"])

                loan_details["total_repaid"] = total_repaid
                loan_details["remaining_balance"] = max(float(loan["loan_amount"]) - total_repaid, 0)
            else:
                loan_details["repayment_records"] = []
                loan_details["total_repaid"] = 0
                loan_details["remaining_balance"] = max(float(loan["loan_amount"]), 0)

            # Add next installment calculation (EMI, capped by remaining)
            principal = float(loan.get("loan_amount") or 0)
            months = int(loan.get("loan_term_months") or 0)
            rate = float(loan.get("interest_rate") or 0)
            remaining = loan_details["remaining_balance"]
            monthly_rate = rate / (12 * 100) if months else 0
            if principal > 0 and months > 0:
                if monthly_rate > 0:
                    try:
                        pow_term = (1 + monthly_rate) ** months
                        emi = principal * monthly_rate * pow_term / (pow_term - 1)
                    except Exception:
                        emi = principal / months
                else:
                    emi = principal / months
            else:
                emi = 0.0
            next_installment = min(emi, remaining) if remaining > 0 and emi > 0 else (0.0 if remaining <= 0 else remaining)
            loan_details["next_installment"] = round(next_installment, 2)

            # NEW: auto-complete status if fully repaid
            try:
                if loan_details.get("status") == "approved" and loan_details["remaining_balance"] <= 0:
                    supabase.table("loans").update({"status": "completed"}).eq("id", loan_details["id"]).execute()
                    loan_details["status"] = "completed"
            except Exception as e:
                print(f"Auto-complete update failed for loan {loan_details.get('id')}: {e}")

            # Fetch staff details if available
            if loan.get("staff_email"):
                staff_resp = supabase.table("staff").select("name,phone,email").eq("email", loan["staff_email"]).execute()
                if staff_resp.data:
                    loan_details["staff_details"] = staff_resp.data[0]
                else:
                    loan_details["staff_details"] = {
                        "name": loan.get("staff_name"),
                        "phone": loan.get("staff_phone"),
                        "email": loan.get("staff_email")
                    }
            else:
                loan_details["staff_details"] = None

            # Fetch sureties for this loan
            sureties_resp = supabase.table("sureties").select("*").eq("loan_id", loan["id"]).execute()
            loan_details["sureties"] = sureties_resp.data if sureties_resp.data else []

            loans_with_details.append(loan_details)

    # Calculate summary statistics
    total_loans = len(loans_with_details)
    active_loans = len([loan for loan in loans_with_details if loan.get("status") == "approved"])
    pending_loans = len([loan for loan in loans_with_details if loan.get("status") == "pending_approval"])
    rejected_loans = len([loan for loan in loans_with_details if loan.get("status") == "rejected"])
    # FIX: complete broken line and include completed loans in aggregates
    total_loan_amount = sum(
        float(loan["loan_amount"]) for loan in loans_with_details if loan.get("status") in ("approved", "completed")
    )
    total_repaid_amount = sum(loan.get("total_repaid", 0) for loan in loans_with_details)
    total_outstanding = sum(
        loan.get("remaining_balance", 0) for loan in loans_with_details if loan.get("status") in ("approved", "completed")
    )

    # Fetch transactions
    transactions_resp = supabase.table("transactions").select("*").eq("customer_id", customer_id).order("date", desc=True).execute()
    transactions = transactions_resp.data if transactions_resp.data else []

    response_data = {
        "status": "success",
        "customer": customer_info,
        "loans": loans_with_details,
        "summary": {
            "total_loans": total_loans,
            "active_loans": active_loans,
            "pending_loans": pending_loans,
            "rejected_loans": rejected_loans,
            "total_loan_amount": total_loan_amount,
            "total_repaid_amount": total_repaid_amount,
            "total_outstanding": total_outstanding
        },
        "transactions": transactions
    }
    return jsonify(response_data), 200
@finance_bp.route('/loan-repayment-page')
def loan_repayment_page():
    return render_template('loan_repayment.html')

@finance_bp.route('/repay-loan', methods=['POST'])
def repay_loan():
    """
    API to make a loan repayment.
    """
    try:
        data = request.get_json() or {}
        loan_id = data.get("loan_id")

        def safe_float(val):
            try:
                if val is None or val == "" or str(val).lower() == "none":
                    return 0.0
                return float(val)
            except Exception:
                return 0.0

        custom_amount = safe_float(data.get("amount"))
        # principal_part and interest_part are not stored in DB, only used for UI breakdown
        principal_part = safe_float(data.get("principal_amount"))
        interest_part = safe_float(data.get("interest_amount"))
        repayment_date = data.get("repayment_date") or datetime.now().date().isoformat()

        if not loan_id or custom_amount <= 0:
            return jsonify({"status": "error", "message": "Missing loan_id or amount"}), 400

        # Fetch loan details
        loan_resp = supabase.table("loans").select("*").eq("id", loan_id).execute()
        if not loan_resp.data:
            loan_resp = supabase.table("loans").select("*").eq("loan_id", loan_id).execute()
            if not loan_resp.data:
                return jsonify({"status": "error", "message": "Loan not found"}), 404
        loan = loan_resp.data[0]

        # Fetch summary row from loan_records (see previous fix)
        loan_records_resp = supabase.table("loan_records").select("*").eq("loan_id", loan.get("loan_id")).execute()
        loan_records = loan_records_resp.data or []
        summary = None
        for rec in loan_records:
            if rec.get("repayment_amount") is None:
                summary = rec
                break
        if not summary:
            loan_records_resp2 = supabase.table("loan_records").select("*").eq("loan_id", loan_id).execute()
            loan_records2 = loan_records_resp2.data or []
            for rec in loan_records2:
                if rec.get("repayment_amount") is None:
                    summary = rec
                    break
        if not summary:
            return jsonify({"status": "error", "message": "Loan summary record not found"}), 404

        outstanding = safe_float(summary.get("outstanding_balance"))
        interest_amount = safe_float(summary.get("interest_amount"))

        # Don't allow overpayment or zero/negative repayments
        if outstanding <= 0 or custom_amount <= 0:
            return jsonify({"status": "error", "message": "No outstanding balance or invalid amount."}), 400

        repayment_amount = min(custom_amount, outstanding)

        # If principal/interest split not provided or invalid, calculate proportionally
        if principal_part < 0 or interest_part < 0 or abs(principal_part + interest_part - repayment_amount) > 0.01:
            principal = safe_float(loan.get("loan_amount"))
            total_interest = safe_float(summary.get("interest_amount"))
            total_out = principal + total_interest
            if total_out > 0:
                principal_part = round(repayment_amount * (principal / total_out), 2)
                interest_part = round(repayment_amount * (total_interest / total_out), 2)
            else:
                principal_part = repayment_amount
                interest_part = 0.0

        # Ensure no negative splits
        if principal_part < 0:
            principal_part = 0.0
        if interest_part < 0:
            interest_part = 0.0
        # Ensure sum matches repayment_amount
        if abs(principal_part + interest_part - repayment_amount) > 0.01:
            # Adjust interest to match
            interest_part = repayment_amount - principal_part

        new_outstanding = max(outstanding - repayment_amount, 0)

        # Insert repayment record (now includes principal_amount column)
        supabase.table("loan_records").insert({
            "loan_id": loan.get("loan_id"),
            "repayment_date": repayment_date,
            "repayment_amount": repayment_amount,
            "principal_amount": principal_part,
            "outstanding_balance": new_outstanding,
            "status": "completed" if new_outstanding == 0 else "active",
            "interest_amount": interest_part
        }).execute()

        supabase.table("loan_records").update({
            "outstanding_balance": new_outstanding,
            "interest_amount": max(safe_float(summary.get("interest_amount")) - interest_part, 0)
        }).eq("id", summary["id"]).execute()



        # Send repayment email with repayment certificate download URL (no PDF attachment)
        member_email = None
        member_name = None
        member_resp = supabase.table("members").select("email,name").eq("customer_id", loan["customer_id"]).execute()
        if member_resp.data and member_resp.data[0].get("email"):
            member_email = member_resp.data[0]["email"]
            member_name = member_resp.data[0].get("name") or "Member"

        # Fetch the latest repayment record to get its ID
        repayment_record_resp = supabase.table("loan_records").select("id").eq("loan_id", loan.get("loan_id")).order("repayment_date", desc=True).limit(1).execute()
        repayment_id = None
        if repayment_record_resp.data and len(repayment_record_resp.data) > 0:
            repayment_id = repayment_record_resp.data[0]["id"]

        # Build repayment certificate URL (public site)
        base_url = "https://ksthstsociety.com"
        if repayment_id:
            certificate_url = f"{base_url}/loan/repayment-certificate/{repayment_id}?action=view"
        else:
            certificate_url = ""

        # Send email with repayment certificate link (no PDF)
        if member_email and certificate_url:
            EMAIL_USER = os.environ.get("EMAIL_USER")
            EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
            if EMAIL_USER and EMAIL_PASSWORD:
                from email.mime.text import MIMEText
                import smtplib
                subject = f"Loan Repayment Certificate - {loan.get('loan_id')}"
                body = (
                    f"Dear {member_name},\n\n"
                    f"Your loan repayment has been received. You can view and download your repayment certificate at the following link:\n"
                    f"{certificate_url}\n\nThank you."
                )
                msg = MIMEText(body)
                msg['Subject'] = subject
                msg['From'] = EMAIL_USER
                msg['To'] = member_email
                try:
                    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                        server.login(EMAIL_USER, EMAIL_PASSWORD)
                        server.sendmail(EMAIL_USER, [member_email], msg.as_string())
                except Exception as e:
                    current_app.logger.error(f"Failed to send repayment certificate email: {e}")

        if new_outstanding == 0 and loan.get("status") == "approved":
            supabase.table("loans").update({"status": "completed"}).eq("id", loan["id"]).execute()

        # Build repayment certificate URL with action=view for API response
        from flask import url_for
        if repayment_id:
            certificate_url = url_for(
                'finance.repayment_certificate',
                repayment_id=repayment_id,
                action='view',
                _external=True
            )
        else:
            certificate_url = ""

        return jsonify({
            "status": "success",
            "message": "Repayment successful",
            "repayment_amount": repayment_amount,
            "principal_amount": principal_part,  # for UI only
            "interest_amount": interest_part,    # for UI only
            "outstanding_balance": new_outstanding,
            "certificate_url": certificate_url,
            "repayment_id": repayment_id
        }), 200

    except Exception as e:
        import traceback
        print("Error in repay_loan:", e)
        print(traceback.format_exc())
        return jsonify({"status": "error", "message": str(e)}), 500

from flask import request, jsonify

@finance_bp.route('/api/check-civil-score', methods=['GET'])
def check_civil_score():
    """
    Check civil score for a customer by customer_id or kgid.
    Returns: { status, score, message, details }
    """
    customer_id = request.args.get('customer_id')
    kgid = request.args.get('kgid')
    if not customer_id and not kgid:
        return jsonify({"status": "error", "message": "customer_id or kgid required"}), 400

    # Fetch customer by customer_id or kgid
    customer = None
    if customer_id:
        resp = supabase.table("members").select("*").eq("customer_id", customer_id).execute()
        if resp.data:
            customer = resp.data[0]
    elif kgid:
        resp = supabase.table("members").select("*").eq("kgid", kgid).execute()
        if resp.data:
            customer = resp.data[0]
    if not customer:
        return jsonify({"status": "error", "message": "Customer not found"}), 404

    # Fetch all loans for this customer
    loans_resp = supabase.table("loans").select("*").eq("customer_id", customer["customer_id"]).execute()
    loans = loans_resp.data or []

    # Analyze each loan's repayment history
    civil_results = []
    for loan in loans:
        loan_id = loan.get("loan_id") or loan.get("id")
        loan_term = int(loan.get("loan_term_months") or 0)
        # Fetch all repayments for this loan
        records_resp = supabase.table("loan_records").select("*").eq("loan_id", loan_id).execute()
        records = [r for r in (records_resp.data or []) if r.get("repayment_amount") not in (None, "")]
        if not records:
            continue
        # Find first and last repayment date
        repayment_dates = sorted([r["repayment_date"] for r in records if r.get("repayment_date")])
        if not repayment_dates:
            continue
        first_date = repayment_dates[0]
        last_date = repayment_dates[-1]
        # Calculate months taken to repay (difference in months)
        from datetime import datetime
        try:
            d1 = datetime.strptime(first_date, "%Y-%m-%d")
            d2 = datetime.strptime(last_date, "%Y-%m-%d")
            months_taken = (d2.year - d1.year) * 12 + (d2.month - d1.month) + 1
        except Exception:
            months_taken = loan_term
        # Only consider fully repaid loans
        outstanding = 0
        for r in records:
            if r.get("outstanding_balance") is not None:
                try:
                    outstanding = float(r["outstanding_balance"])
                except Exception:
                    outstanding = 0
        fully_repaid = outstanding == 0
        if not fully_repaid:
            continue
        # Score logic
        if months_taken < loan_term:
            score = "EXCELLENT"
            msg = f"Loan {loan_id}: Repaid in {months_taken} months (before {loan_term} months)."
        elif months_taken == loan_term:
            score = "GOOD"
            msg = f"Loan {loan_id}: Repaid on time ({months_taken} months)."
        else:
            score = "AVERAGE"
            msg = f"Loan {loan_id}: Repaid in {months_taken} months (after term)."
        civil_results.append({
            "loan_id": loan_id,
            "loan_term": loan_term,
            "months_taken": months_taken,
            "score": score,
            "message": msg
        })

    # Determine overall score
    if not civil_results:
        return jsonify({
            "status": "success",
            "score": "NO HISTORY",
            "message": "No fully repaid loans found for this customer.",
            "details": []
        })
    # If any EXCELLENT, show EXCELLENT, else if any GOOD, show GOOD, else AVERAGE
    overall = "AVERAGE"
    for r in civil_results:
        if r["score"] == "EXCELLENT":
            overall = "EXCELLENT"
            break
        elif r["score"] == "GOOD":
            overall = "GOOD"
    if overall == "EXCELLENT":
        msg = "Excellent repayment history. Can provide loan with less interest rate."
    elif overall == "GOOD":
        msg = "Good repayment history. Can provide loan."
    else:
        msg = "Average repayment history."

    return jsonify({
        "status": "success",
        "score": overall,
        "message": msg,
        "details": civil_results
    })
@finance_bp.route('/fd/certificate/<fdid>')
def fd_certificate(fdid):
    """
    View / print / download / json FD certificate.
    action=view|download|print|json
    """
    action = request.args.get('action', 'view')
    fd_resp = supabase.table("fixed_deposits").select("*").eq("fdid", fdid).limit(1).execute()
    if not fd_resp.data:
        return jsonify({"status": "error", "message": "FD not found"}), 404
    fd = fd_resp.data[0]

    # Member
    member_resp = supabase.table("members").select("customer_id,name,kgid,phone,email,aadhar_no,pan_no").eq("customer_id", fd.get("customer_id")).limit(1).execute()
    member = member_resp.data[0] if member_resp.data else {}

    # Interest / maturity calculations
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
    from datetime import datetime
    if fd.get("deposit_date"):
        try:
            d = datetime.strptime(fd["deposit_date"], "%Y-%m-%d")
            year = d.year + (d.month - 1 + tenure_m) // 12
            month = (d.month - 1 + tenure_m) % 12 + 1
            day = min(d.day, 28)
            maturity_date = f"{year:04d}-{month:02d}-{day:02d}"
        except Exception:
            maturity_date = None

    cert_ctx = dict(
        fd=fd,
        member=member,
        principal=principal,
        rate=rate,
        tenure_months=tenure_m,
        interest=interest,
        maturity_amount=maturity_amount,
        maturity_date=maturity_date,
        amount_words=amount_to_words(maturity_amount),
        society_name="KSTHST Coof Society",
        taluk_name="Taluk",
        district_name="District"
    )

    if action == "json":
        return jsonify({"status": "success", **cert_ctx}), 200

    html = render_template("fd_certificate.html", **cert_ctx)

    if action == "download":
        resp = make_response(html)
        resp.headers['Content-Type'] = 'text/html; charset=utf-8'
        resp.headers['Content-Disposition'] = f'attachment; filename=fd_{fdid}.html'
        return resp
    if action == "print":
        html += "<script>window.onload=function(){window.print();}</script>"
        return html
    return html