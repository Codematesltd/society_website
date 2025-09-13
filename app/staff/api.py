import os
import uuid
import re
import pandas as pd
import random
from flask import Blueprint, request, jsonify, render_template, make_response, abort, session, url_for, redirect, current_app
from app.auth.decorators import login_required, role_required
from werkzeug.utils import secure_filename
from io import BytesIO
from supabase import create_client, Client
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from PIL import Image
from datetime import datetime, timedelta
from xhtml2pdf import pisa
import inflect
from httpx import RemoteProtocolError

staff_api_bp = Blueprint('staff_api', __name__, url_prefix='/staff/api')
@staff_api_bp.route('/recent-transactions/excel', methods=['GET'])
@login_required
@role_required('admin', 'staff')
def export_recent_transactions_excel():
    """
    Export recent transactions as Excel (.xlsx) for staff.
    Aggregates data from transactions, loans, loan_records, expenses, and staff_salaries tables.
    Query params: year, month, day (all optional)
    Returns: Excel file with all transaction types
    """
    try:
        year = request.args.get('year')
        month = request.args.get('month')
        day = request.args.get('day')
        
        # Build date range
        if day and month and year:
            # Specific day
            start_str = f"{year}-{int(month):02d}-{int(day):02d}"
            end_dt = datetime.strptime(start_str, '%Y-%m-%d') + timedelta(days=1)
            end_str = end_dt.strftime('%Y-%m-%d')
        elif month and year:
            # Specific month
            start_str = f"{year}-{int(month):02d}-01"
            if int(month) == 12:
                end_str = f"{int(year)+1}-01-01"
            else:
                end_str = f"{year}-{int(month)+1:02d}-01"
        elif year:
            # Specific year
            start_str = f"{year}-01-01"
            end_str = f"{int(year)+1}-01-01"
        else:
            # Current year if no params
            now = datetime.utcnow()
            start_str = f"{now.year}-01-01"
            end_str = f"{now.year+1}-01-01"

        excel_data = []

        # 1) Deposits & Withdrawals from transactions
        try:
            tx_query = supabase.table('transactions').select('type,amount,date,customer_id,transaction_id')
            tx_query = tx_query.gte('date', start_str).lt('date', end_str)
            tx_resp = tx_query.order('date', desc=True).limit(1000).execute()
            txs = tx_resp.data if hasattr(tx_resp, 'data') and tx_resp.data else []
            for tx in txs:
                ttype = str(tx.get('type') or '').lower()
                if ttype not in ('deposit', 'withdraw', 'withdrawal'):
                    continue
                label = 'Deposit' if ttype == 'deposit' else 'Withdrawal'
                try:
                    amt = float(tx.get('amount') or 0)
                except Exception:
                    amt = 0.0
                excel_data.append({
                    'Date': str(tx.get('date') or ''),
                    'Type': label,
                    'Amount': round(amt, 2),
                    'Details': f"Customer: {tx.get('customer_id') or '-'}",
                    'Reference ID': tx.get('transaction_id')
                })
        except Exception:
            pass

        # 2) Loan approvals from loans
        try:
            loan_resp = supabase.table('loans') \
                .select('loan_id,customer_id,loan_amount,status,created_at') \
                .gte('created_at', start_str).lt('created_at', end_str).execute()
            loans = loan_resp.data if hasattr(loan_resp, 'data') and loan_resp.data else []
            for ln in loans:
                status = str(ln.get('status') or '').lower()
                if status == 'approved':
                    try:
                        amt = float(ln.get('loan_amount') or 0)
                    except Exception:
                        amt = 0.0
                    excel_data.append({
                        'Date': str(ln.get('created_at') or ''),
                        'Type': 'Loan Approved',
                        'Amount': round(amt, 2),
                        'Details': f"Customer: {ln.get('customer_id') or '-'}",
                        'Reference ID': ln.get('loan_id')
                    })
        except Exception:
            pass

        # 3) Loan repayments from loan_records
        try:
            rec_resp = supabase.table('loan_records') \
                .select('loan_id,repayment_amount,repayment_date') \
                .gte('repayment_date', start_str).lt('repayment_date', end_str).execute()
            recs = rec_resp.data if hasattr(rec_resp, 'data') and rec_resp.data else []
            for r in recs:
                try:
                    amt = float(r.get('repayment_amount') or 0)
                except Exception:
                    amt = 0.0
                if amt <= 0:
                    continue
                excel_data.append({
                    'Date': str(r.get('repayment_date') or ''),
                    'Type': 'Loan Repayment',
                    'Amount': round(amt, 2),
                    'Details': f"Loan: {r.get('loan_id') or '-'}",
                    'Reference ID': r.get('loan_id')
                })
        except Exception:
            pass

        # 4) Expenses
        try:
            exp_resp = supabase.table('expenses') \
                .select('id,amount,date,name') \
                .gte('date', start_str).lt('date', end_str).execute()
            exps = exp_resp.data if hasattr(exp_resp, 'data') and exp_resp.data else []
            for e in exps:
                try:
                    amt = float(e.get('amount') or 0)
                except Exception:
                    amt = 0.0
                excel_data.append({
                    'Date': str(e.get('date') or ''),
                    'Type': 'Expense',
                    'Amount': round(amt, 2),
                    'Details': e.get('name') or 'Expense',
                    'Reference ID': e.get('id')
                })
        except Exception:
            pass

        # 5) Staff salaries  
        try:
            sal_resp = supabase.table('staff_salaries') \
                .select('name,kgid,salary,date,transaction_id') \
                .gte('date', start_str).lt('date', end_str).execute()
            rows = sal_resp.data if hasattr(sal_resp, 'data') and sal_resp.data else []
            for s in rows:
                try:
                    amt = float(s.get('salary') or 0)
                except Exception:
                    amt = 0.0
                who = s.get('name') or s.get('kgid') or 'Staff'
                excel_data.append({
                    'Date': str(s.get('date') or ''),
                    'Type': 'Staff Salary',
                    'Amount': round(amt, 2),
                    'Details': str(who),
                    'Reference ID': s.get('transaction_id')
                })
        except Exception:
            pass

        # Sort by date descending
        excel_data.sort(key=lambda x: str(x.get('Date') or ''), reverse=True)

        if not excel_data:
            return jsonify({'status': 'error', 'message': 'No transactions found for the specified period'}), 404

        # Create DataFrame and Excel file
        df = pd.DataFrame(excel_data)
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Recent Transactions")
        output.seek(0)
        
        response = make_response(output.read())
        response.headers["Content-Disposition"] = "attachment; filename=recent_transactions_staff.xlsx"
        response.headers["Content-Type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        return response
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Failed to generate Excel: {str(e)}'}), 500
staff_bp = Blueprint('staff', __name__, url_prefix='/staff')

@staff_api_bp.route('/admin/recent-transactions/excel', methods=['GET'])
@login_required
def export_recent_transactions_excel_admin():
    """
    Export recent transactions as Excel (.xlsx) for admin.
    Query params: year, month, day (all optional)
    Returns: Excel file
    """
    year = request.args.get('year')
    month = request.args.get('month')
    day = request.args.get('day')
    tx_query = supabase.table("transactions").select("*")
    # Date filtering
    if year:
        tx_query = tx_query.gte("date", f"{year}-01-01").lte("date", f"{year}-12-31")
    if month and year:
        from_month = f"{year}-{int(month):02d}-01"
        if int(month) == 12:
            to_month = f"{int(year)+1}-01-01"
        else:
            to_month = f"{year}-{int(month)+1:02d}-01"
        tx_query = tx_query.gte("date", from_month).lt("date", to_month)
    if day and month and year:
        date_str = f"{year}-{int(month):02d}-{int(day):02d}"
        tx_query = tx_query.eq("date", date_str)
    tx_resp = tx_query.order("date", desc=True).limit(1000).execute()
    txs = tx_resp.data or []
    if not txs:
        return jsonify({"status": "error", "message": "No transactions found for export."}), 404
    # Prepare DataFrame
    df = pd.DataFrame(txs)
    columns = [
        ("date", "Date"),
        ("stid", "STID"),
        ("type", "Type"),
        ("amount", "Amount"),
        ("from_account", "From Account"),
        ("to_account", "To Account"),
        ("from_bank_name", "From Bank"),
        ("to_bank_name", "To Bank"),
        ("remarks", "Remarks"),
        ("customer_id", "Customer ID"),
        ("balance_after", "Balance After"),
    ]
    col_map = {k: v for k, v in columns}
    df = df[[k for k, _ in columns if k in df.columns]].rename(columns=col_map)
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Transactions")
    output.seek(0)
    response = make_response(output.read())
    response.headers["Content-Disposition"] = "attachment; filename=recent_transactions_admin.xlsx"
    response.headers["Content-Type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return response


load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
SUPABASE_BUCKET = "staff-add"
STORAGE_PUBLIC_PATH = f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_BUCKET}"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
p = inflect.engine()

def send_otp_email(email, otp):
    EMAIL_USER = os.getenv("EMAIL_USER")
    EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
    if not EMAIL_USER or not EMAIL_PASSWORD:
        raise RuntimeError("EMAIL_USER and EMAIL_PASSWORD must be set in environment")
    subject = "Membership Registration OTP"
    body = (
        f"Your OTP for membership registration is: {otp}\n\n"
        f"Please provide this OTP to the staff member assisting you with your registration.\n"
        f"This OTP is valid for a limited time only.\n\n"
        "Thank you.\n"
    )
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = EMAIL_USER
    msg['To'] = email
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.send_message(msg)
    except smtplib.SMTPException as e:
        raise RuntimeError(f"SMTP error: {e}")

@staff_api_bp.route('/statements', methods=['GET'])
@login_required
@role_required('staff')
def staff_statements():
    """
    Staff API to fetch member statements by customer_id.
    Query params:
      - customer_id: required
      - range: 'last10' (default), '1m', '3m', '6m', '1y', 'custom'
      - from_date: (YYYY-MM-DD, required if range=custom)
      - to_date: (YYYY-MM-DD, required if range=custom)
      - format: 'pdf' to get PDF version
    Returns: { "status": "success", "transactions": [...] } or PDF file
    """
    customer_id = request.args.get('customer_id')
    format = request.args.get('format')
    if not customer_id:
        return jsonify({"status": "error", "message": "customer_id is required"}), 400

    # Verify the member exists and get current balance
    member_resp = supabase.table("members").select("customer_id,balance").eq("customer_id", customer_id).execute()
    if not member_resp.data:
        return jsonify({"status": "error", "message": "Member not found"}), 404
    current_balance = float(member_resp.data[0].get("balance") or 0)

    # Parse query params
    range_type = request.args.get("range", "last10")
    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")

    now = datetime.now()
    date_col = "date"  # transactions use 'date' column

    # Fetch transactions for the member
    tx_query = supabase.table("transactions").select("*")
    tx_query = tx_query.eq("customer_id", customer_id)

    # Date filtering
    if range_type == "custom" and from_date and to_date:
        try:
            from_dt = datetime.strptime(from_date, "%Y-%m-%d")
            to_dt = datetime.strptime(to_date, "%Y-%m-%d")
            tx_query = tx_query.gte(date_col, from_date).lte(date_col, to_date)
        except Exception:
            return jsonify({"status": "error", "message": "Invalid date format for custom range"}), 400
    elif range_type == "1m":
        since = (now - timedelta(days=30)).strftime("%Y-%m-%d")
        tx_query = tx_query.gte(date_col, since)
    elif range_type == "3m":
        since = (now - timedelta(days=90)).strftime("%Y-%m-%d")
        tx_query = tx_query.gte(date_col, since)
    elif range_type == "6m":
        since = (now - timedelta(days=180)).strftime("%Y-%m-%d")
        tx_query = tx_query.gte(date_col, since)
    elif range_type == "1y":
        since = (now - timedelta(days=365)).strftime("%Y-%m-%d")
        tx_query = tx_query.gte(date_col, since)
    # else: last10 handled after fetch

    tx_resp = tx_query.execute()
    events = tx_resp.data or []

    # Sort by date desc (newest first)
    events.sort(key=lambda e: str(e.get("date") or ""), reverse=True)

    # If last10 requested, slice top 10 events
    if range_type == "last10":
        events = events[:10]

    # Compute running balance_after for each event using current_balance (walk from newest -> oldest)
    running = float(current_balance or 0)
    for ev in events:
        # set balance as snapshot after this event (newest first)
        ev["balance_after"] = round(running, 2)
        amt = float(ev.get("amount") or 0)
        # when moving backwards: deposits increase balance going forward, so subtract deposit to step back
        if ev.get("type") == "deposit":
            running = round(running - amt, 2)
        else:
            # withdraw/withdrawal types assumed to reduce balance going forward, so add back when stepping back
            running = round(running + amt, 2)

    # If PDF requested, render statement.html and return as PDF
    if format == "pdf":
        # Fetch member details for template
        member_info = supabase.table("members").select("*").eq("customer_id", customer_id).limit(1).execute()
        member = member_info.data[0] if member_info.data else {}
        society_name = os.environ.get("SOCIETY_NAME", "Kushtagi Taluk High School Employees Cooperative Society Ltd., Kushtagi-583277")
        taluk_name = os.environ.get("TALUK_NAME", "Kushtagi")
        district_name = os.environ.get("DISTRICT_NAME", "koppala")
        html = render_template(
            "statement.html",
            member=member,
            transactions=events,
            current_balance=current_balance,
            society_name=society_name,
            taluk_name=taluk_name,
            district_name=district_name,
            from_date=from_date,
            to_date=to_date,
            range_type=range_type
        )
        pdf = BytesIO()
        pisa.CreatePDF(html, dest=pdf)
        response = make_response(pdf.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=statement_{customer_id}.pdf'
        return response

    return jsonify({"status": "success", "transactions": events}), 200
    
@staff_api_bp.route('/loan-info', methods=['GET'])
def loan_info():
    """
    Returns loan info for Loan Info Search panel (by loan_id).
    Adds total_principal_repaid and total_interest_repaid fields.
    """
    loan_id = request.args.get('loan_id')
    if not loan_id:
        return jsonify({'status': 'error', 'message': 'Missing loan_id'}), 400
    # Try to fetch by textual loan_id or UUID
    loan = None
    # Try by loan_id (text)
    resp = supabase.table('loans').select('*').eq('loan_id', loan_id).limit(1).execute()
    if resp.data:
        loan = resp.data[0]
    if not loan:
        # Try by UUID
        resp2 = supabase.table('loans').select('*').eq('id', loan_id).limit(1).execute()
        if resp2.data:
            loan = resp2.data[0]
    if not loan:
        return jsonify({'status': 'error', 'message': 'Loan not found'}), 404

    # Fetch member name
    member_name = None
    if loan.get('customer_id'):
        mresp = supabase.table('members').select('name').eq('customer_id', loan['customer_id']).limit(1).execute()
        if mresp.data:
            member_name = mresp.data[0].get('name')


  
    
    # Fetch all repayments for this loan (by loan_id or UUID)

    recs1 = supabase.table('loan_records').select('*').eq('loan_id', loan.get('loan_id')).execute()
    recs2 = supabase.table('loan_records').select('*').eq('loan_id', loan.get('id')).execute()
    
    
    
    all_records = []
    seen = set()
    for r in (recs1.data or []) + (recs2.data or []):
        rid = r.get('id')
        if rid and rid not in seen:
            all_records.append(r)
            seen.add(rid)
    
    
    if all_records:
        print(f"DEBUG: Sample record: {all_records[0]}")
            
   

    # Calculate totals (ignore nulls, sum only numeric values)
    principal_values = []
    interest_values = []
    for r in all_records:
        if r.get('principal_amount') is not None and r.get('repayment_amount') is not None:
            try:
                principal_values.append(float(r['principal_amount']))
            except (ValueError, TypeError) as e:
                print(f"DEBUG: Error converting principal_amount to float: {r['principal_amount']}, Error: {e}")
                
        if r.get('interest_amount') is not None and r.get('repayment_amount') is not None:
            try:
                interest_values.append(float(r['interest_amount']))
            except (ValueError, TypeError) as e:
                print(f"DEBUG: Error converting interest_amount to float: {r['interest_amount']}, Error: {e}")
    
    print(f"DEBUG: Found {len(principal_values)} valid principal amounts: {principal_values}")
    print(f"DEBUG: Found {len(interest_values)} valid interest amounts: {interest_values}")
    
    total_principal_repaid = sum(principal_values) if principal_values else 0.0
    total_interest_repaid = sum(interest_values) if interest_values else 0.0
    
    print(f"DEBUG: Final totals - Principal: {total_principal_repaid}, Interest: {total_interest_repaid}")

    # Outstanding = last remaining_principal_amount, else loan_amount
    outstanding_amount = loan.get('loan_amount')
    # Find the latest repayment with a non-null remaining_principal_amount
    sorted_records = sorted(
        [r for r in all_records if r.get('repayment_amount') is not None and r.get('remaining_principal_amount') is not None],
        key=lambda x: x.get('repayment_date') or '',
        reverse=True
    )
    if sorted_records:
        outstanding_amount = sorted_records[0]['remaining_principal_amount']

    # Next installment amount (legacy, can be removed from frontend)
    next_installment_amount = None
    if 'next_installment' in loan:
        try:
            next_installment_amount = float(loan['next_installment'])
        except Exception:
            next_installment_amount = None

    info = {
        'name': member_name or '-',
        'loan_amount': loan.get('loan_amount'),
        'loan_term_months': loan.get('loan_term_months'),
        'interest_rate': loan.get('interest_rate'),
        'outstanding_amount': outstanding_amount,
        'total_principal_repaid': total_principal_repaid,
        'total_interest_repaid': total_interest_repaid,
        # 'next_installment_amount': next_installment_amount,  # No longer needed in frontend
    }
    return jsonify({'status': 'success', 'loan_info': info}), 200


@staff_api_bp.route('/add-member/send-otp', methods=['POST'])
def send_member_otp():
    email = request.form.get('email')
    if not email or not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return jsonify({'status': 'error', 'message': 'Invalid email'}), 400
    otp = str(uuid.uuid4().int)[-6:]
    try:
        # Check if member exists
        member_rows = supabase.table("members").select("id").eq("email", email).execute()
        if member_rows.data and len(member_rows.data) > 0:
            # Update OTP only
            supabase.table("members").update({"otp": otp}).eq("email", email).execute()
        else:
            # Insert with required NOT NULL fields as empty strings
            supabase.table("members").insert({
                "name": "",
                "kgid": "",
                "phone": "",
                "email": email,
                "aadhar_no": "",
                "pan_no": "",
                "salary": None,
                "organization_name": "",
                "address": "",
                "photo_url": "",
                "signature_url": "",
                "otp": otp
            }).execute()
        send_otp_email(email, otp)
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Failed to send OTP', 'error': str(e)}), 500
    return jsonify({'status': 'success', 'message': 'OTP sent'})

def compress_image(file_storage, max_size_kb=100):
    img = Image.open(file_storage)
    img_format = img.format if img.format else 'JPEG'
    quality = 85
    buffer = BytesIO()
    img.save(buffer, format=img_format, optimize=True, quality=quality)
    while buffer.tell() > max_size_kb * 1024 and quality > 10:
        quality -= 5
        buffer.seek(0)
        buffer.truncate()
        img.save(buffer, format=img_format, optimize=True, quality=quality)
    buffer.seek(0)
    return buffer

def send_member_otp():
    email = request.form.get('email')
    if not email or not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return jsonify({'status': 'error', 'message': 'Invalid email'}), 400
    
    otp = str(uuid.uuid4().int)[-6:]
    try:
        # Check if member exists
        member_rows = supabase.table("members").select("id").eq("email", email).execute()
        if member_rows.data and len(member_rows.data) > 0:
            # Update OTP only
            supabase.table("members").update({"otp": otp}).eq("email", email).execute()
        else:
            # Insert only email and OTP for a new user.
            # The rest of the data will be added when the form is submitted.
            # We need to provide temporary values for NOT NULL fields
            supabase.table("members").insert({
                "email": email,
                "otp": otp,
                "name": "temp_pending",
                "phone": "temp_pending", 
                "organization_name": "temp_pending",
                "address": "temp_pending",
                "status": "pending_otp"
            }).execute()
        send_otp_email(email, otp)
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Failed to send OTP', 'error': str(e)}), 500
    return jsonify({'status': 'success', 'message': 'OTP sent'})

def compress_image(file_storage, max_size_kb=100):
    img = Image.open(file_storage)
    img_format = img.format if img.format else 'JPEG'
    quality = 85
    buffer = BytesIO()
    img.save(buffer, format=img_format, optimize=True, quality=quality)
    while buffer.tell() > max_size_kb * 1024 and quality > 10:
        quality -= 5
        buffer.seek(0)
        buffer.truncate()
        img.save(buffer, format=img_format, optimize=True, quality=quality)
    buffer.seek(0)
    return buffer

def send_status_email(email, status):
    EMAIL_USER = os.getenv("EMAIL_USER")
    EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
    if not EMAIL_USER or not EMAIL_PASSWORD:
        raise RuntimeError("EMAIL_USER and EMAIL_PASSWORD must be set in environment")
    if status == "pending":
        subject = "Membership Pending Approval"
        body = "Your membership request is pending manager approval."
    elif status == "approved":
        subject = "Membership Approved"
        body = "Congratulations! Your membership has been approved. You can now sign in."
    elif status == "rejected":
        subject = "Membership Rejected"
        body = "Sorry, your membership request has been rejected."
    else:
        subject = "Membership Status Update"
        body = f"Your membership status is now: {status}"
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = EMAIL_USER
    msg['To'] = email
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.send_message(msg)
    except smtplib.SMTPException as e:
        raise RuntimeError(f"SMTP error: {e}")

def generate_customer_id(prefix="KSTHST"):
    """Generate a unique customer ID like ABCDE1234."""
    return f"{prefix}{random.randint(1000, 9999)}"

def generate_stid():
    """Generate a unique Society Transaction ID (STID####), 4-digit sequence, no year."""
    stid_prefix = "STID"
    # Query for the latest stid
    resp = supabase.table("transactions") \
        .select("stid") \
        .like("stid", f"{stid_prefix}%") \
        .order("stid", desc=True) \
        .limit(1) \
        .execute()
    if resp.data and len(resp.data) > 0 and resp.data[0].get("stid"):
        last_stid = resp.data[0]["stid"]
        # Extract the numeric part after STID
        match = re.match(r"STID(\d{4})", last_stid)
        if match:
            seq = int(match.group(1)) + 1
        else:
            seq = 1
    else:
        seq = 1
    return f"STID{seq:04d}"

def generate_system_fdid():
    """Generate next sequential internal system_fdid (formerly fdid) like FD0001, FD0002."""
    resp = supabase.table("fixed_deposits").select("system_fdid").order("id", desc=True).limit(1).execute()
    last_val = None
    if resp.data and resp.data[0].get("system_fdid"):
        last_val = resp.data[0]["system_fdid"]
    if last_val and isinstance(last_val, str) and last_val.startswith("FD"):
        try:
            seq = int(last_val[2:]) + 1
        except Exception:
            seq = 1
    else:
        seq = 1
    return f"FD{seq:04d}"

@staff_api_bp.route('/add-member', methods=['POST'])
def add_member():
    # Use old working logic, kgid optional
    form = {k.strip(): v for k, v in request.form.items()}
    files = {k.strip(): v for k, v in request.files.items()}
    required_fields = ['name', 'phone', 'email', 'aadhar_no', 'pan_no', 'salary', 'organization_name', 'address', 'otp']
    data = {field: form.get(field, '').strip() for field in required_fields}
    kgid = form.get('kgid', '').strip()  # optional

    missing = [f for f, v in data.items() if not v]
    if missing:
        return jsonify({'status': 'error', 'message': f'Missing fields: {", ".join(missing)}'}), 400

    if not re.match(r"[^@]+@[^@]+\.[^@]+", data['email']):
        return jsonify({'status': 'error', 'message': 'Invalid email format'}), 400

    otp = data['otp']
    member_rows = supabase.table("members").select("otp,customer_id").eq("email", data['email']).execute()
    if not member_rows.data or not member_rows.data[0].get("otp"):
        return jsonify({'status': 'error', 'message': 'OTP not found for this email'}), 400
    stored_otp = member_rows.data[0]["otp"]
    if otp != stored_otp:
        return jsonify({'status': 'error', 'message': 'Invalid or expired OTP'}), 400
    supabase.table("members").update({"otp": None}).eq("email", data['email']).execute()

    photo = files.get('photo')
    signature = files.get('signature')
    if not photo or photo.filename == "":
        return jsonify({'status': 'error', 'message': 'Missing or empty photo file'}), 400
    if not signature or signature.filename == "":
        return jsonify({'status': 'error', 'message': 'Missing or empty signature file'}), 400

    allowed_types = {'image/jpeg', 'image/png', 'image/jpg'}
    if photo.mimetype not in allowed_types:
        return jsonify({'status': 'error', 'message': 'Photo must be a JPEG or PNG image'}), 400
    if signature.mimetype not in allowed_types:
        return jsonify({'status': 'error', 'message': 'Signature must be a JPEG or PNG image'}), 400

    max_size = 2 * 1024 * 1024
    photo.seek(0, 2)
    photo_size = photo.tell()
    photo.seek(0)
    signature.seek(0, 2)
    signature_size = signature.tell()
    signature.seek(0)
    if photo_size > max_size:
        return jsonify({'status': 'error', 'message': 'Photo file too large (max 2MB)'}), 400
    if signature_size > max_size:
        return jsonify({'status': 'error', 'message': 'Signature file too large (max 2MB)'}), 400

    photo_filename = f"{uuid.uuid4().hex}_{secure_filename(photo.filename)}"
    signature_filename = f"{uuid.uuid4().hex}_{secure_filename(signature.filename)}"

    try:
        photo_buffer = compress_image(photo)
        signature_buffer = compress_image(signature)
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Image processing failed', 'error': str(e)}), 400

    try:
        bucket = supabase.storage.from_(SUPABASE_BUCKET)
        bucket.upload(photo_filename, photo_buffer.read())
        bucket.upload(signature_filename, signature_buffer.read())
        photo_url = f"{STORAGE_PUBLIC_PATH}/{photo_filename}"
        signature_url = f"{STORAGE_PUBLIC_PATH}/{signature_filename}"
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Image upload failed', 'error': str(e)}), 500

    member_data = {
        "name": data['name'],
        "kgid": kgid,  # optional
        "phone": data['phone'],
        "email": data['email'],
        "aadhar_no": data['aadhar_no'],
        "pan_no": data['pan_no'],
        "salary": data['salary'],
        "organization_name": data['organization_name'],
        "address": data['address'],
        "photo_url": photo_url,
        "signature_url": signature_url,
        "status": "pending"
    }

    customer_id = member_rows.data[0].get("customer_id") if member_rows.data and "customer_id" in member_rows.data[0] else None
    if not customer_id:
        for _ in range(5):
            new_customer_id = generate_customer_id()
            exists = supabase.table("members").select("id").eq("customer_id", new_customer_id).execute()
            if not exists.data:
                customer_id = new_customer_id
                break
        else:
            return jsonify({'status': 'error', 'message': 'Could not generate unique customer ID'}), 500
        member_data["customer_id"] = customer_id

    try:
        insert_resp = supabase.table("members").upsert(
            member_data,
            on_conflict="email"
        ).execute()
        if not insert_resp.data or len(insert_resp.data) == 0:
            raise Exception("Failed to insert/update member record")
        member_data['id'] = insert_resp.data[0]['id']
        member_data['customer_id'] = insert_resp.data[0].get('customer_id', customer_id)
        send_status_email(member_data['email'], "pending")
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Database insert failed', 'error': str(e)}), 500

    return jsonify({'status': 'success', 'member': member_data}), 201

@staff_api_bp.route('/unblock-member', methods=['POST'])
def staff_unblock_member():
    email = request.form.get('email')
    if not email:
        return jsonify({'status': 'error', 'message': 'Email required'}), 400
    try:
        resp = supabase.table("members").update({"blocked": False, "login_attempts": 0}).eq("email", email).execute()
        if not resp.data or len(resp.data) == 0:
            return jsonify({'status': 'error', 'message': 'Member not found'}), 404
        return jsonify({'status': 'success', 'message': 'Member account unblocked'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Failed to unblock member', 'error': str(e)}), 500

def send_transaction_email(email, name, stid, tx_type, amount, balance_after, receipt_url):
    EMAIL_USER = os.getenv("EMAIL_USER")
    EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
    if not EMAIL_USER or not EMAIL_PASSWORD:
        raise RuntimeError("EMAIL_USER and EMAIL_PASSWORD must be set in environment")
    subject = f"Your {tx_type.title()} Transaction Receipt (STID: {stid})"
    body = (
        f"Dear {name},\n\n"
        f"Your {tx_type} transaction of Rs. {amount} has been processed.\n"
        f"Balance after transaction: Rs. {balance_after}\n"
        f"View/download your receipt: {receipt_url}\n\n"
        "Thank you.\n"
    )
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = EMAIL_USER
    msg['To'] = email
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.send_message(msg)
    except smtplib.SMTPException as e:
        print(f"SMTP error: {e}")

@staff_api_bp.route('/add-transaction', methods=['POST'])
def add_transaction():
    required_fields = [
        "customer_id", "type", "amount",
        "from_account", "to_account", "date", "transaction_id",
        "from_bank_name", "to_bank_name"  # <-- Add these as required
    ]
    data = {field: request.form.get(field) for field in required_fields}
    missing = [f for f, v in data.items() if not v]
    if missing:
        return jsonify({'status': 'error', 'message': f'Missing fields: {", ".join(missing)}'}), 400

    # Optional remarks
    data["remarks"] = request.form.get("remarks", "")

    # Remove all staff_name, staff_email, staff_signature logic
    # Do not set data["staff_name"] or data["staff_email"]

    # Get current balance and share_amount from members table using customer_id
    customer_id = data["customer_id"]
    member_row = supabase.table("members").select("balance,share_amount,name,email").eq("customer_id", customer_id).execute()
    if not member_row.data:
        return jsonify({"status": "error", "message": "Member not found"}), 404
    
    member = member_row.data[0]
    current_balance = float(member.get("balance") or 0)
    current_share_amount = float(member.get("share_amount") or 0)
    max_share = 30000.0

    # Calculate new balance and share_amount
    try:
        amount = float(data["amount"])
    except Exception:
        return jsonify({"status": "error", "message": "Invalid amount"}), 400

    if data["type"] == "deposit":
        # Fill share_amount first up to 30,000, then excess to balance
        if current_share_amount < max_share:
            to_share = min(amount, max_share - current_share_amount)
            to_balance = amount - to_share
            new_share_amount = current_share_amount + to_share
            new_balance = current_balance + (to_balance if to_balance > 0 else 0)
            print(f"DEBUG DEPOSIT: amount={amount}, current_share={current_share_amount}, to_share={to_share}, to_balance={to_balance}, new_share={new_share_amount}, new_balance={new_balance}")
        else:
            to_share = 0
            to_balance = amount
            new_share_amount = current_share_amount
            new_balance = current_balance + amount
            print(f"DEBUG DEPOSIT (share full): amount={amount}, all to balance, new_balance={new_balance}")
    elif data["type"] == "withdraw":
        # Only withdraw from balance
        if amount > current_balance:
            return jsonify({"status": "error", "message": "Insufficient balance"}), 400
        new_balance = current_balance - amount
        new_share_amount = current_share_amount
        print(f"DEBUG WITHDRAW: amount={amount}, current_balance={current_balance}, new_balance={new_balance}, share_amount unchanged={new_share_amount}")
    else:
        return jsonify({"status": "error", "message": "Invalid transaction type"}), 400

    # Add balance_after to transaction data (remove share_amount_after for now)
    data["balance_after"] = new_balance
    # Note: share_amount_after not added to transaction record as column may not exist

    # Generate unique stid for this transaction
    try:
        data["stid"] = generate_stid()
    except Exception as e:
        return jsonify({"status": "error", "message": f"Failed to generate STID: {e}"}), 500

    # Insert transaction
    try:
        resp = supabase.table("transactions").insert(data).execute()
        # Update member's balance and share_amount using customer_id with explicit numeric conversion
        update_data = {
            "balance": float(new_balance),
            "share_amount": float(new_share_amount)
        }
        member_update = supabase.table("members").update(update_data).eq("customer_id", customer_id).execute()
        
        # Check if member update was successful
        if not member_update.data:
            return jsonify({"status": "error", "message": "Failed to update member balance"}), 500
        # Generate receipt URL
        stid = data["stid"]
        receipt_url = f"{os.environ.get('BASE_URL', 'https://ksthstsociety.com')}/staff/transaction/certificate/{stid}?action=view"
        # Send email notification using member data we already have
        member_email = member.get("email")
        member_name = member.get("name", "")
        if member_email:
            try:
                send_transaction_email(
                    member_email,
                    member_name,
                    stid,
                    data["type"],
                    data["amount"],
                    new_balance,
                    receipt_url
                )
            except Exception as e:
                print(f"Failed to send transaction email: {e}")
        # Generate certificate HTML for immediate display
        tx_resp = supabase.table("transactions").select("*").eq("stid", stid).execute()
        tx = tx_resp.data[0] if tx_resp.data else {}
        member = get_member_by_customer_id(tx.get("customer_id", "")) if tx else None
        staff_email = session.get("staff_email")
        staff = get_staff_by_email(staff_email) if staff_email else {}
        # Add staff_signature_url and staff_name for template compatibility
        staff_signature_url = staff.get("signature_url") if staff else None
        staff_name = staff.get("name") if staff else None
        society_name = os.environ.get("SOCIETY_NAME", "Kushtagi Taluk High School Employees Cooperative Society Ltd., Kushtagi-583277")
        taluk_name = os.environ.get("TALUK_NAME", "Kushtagi")
        district_name = os.environ.get("DISTRICT_NAME", "koppala")
        template_data = dict(
            transaction=tx,
            member=member,
            staff=staff,
            staff_signature_url=staff_signature_url,
            staff_name=staff_name,
            society_name=society_name,
            taluk_name=taluk_name,
            district_name=district_name,
            amount_words=amount_to_words(tx.get("amount", 0))
        )
        certificate_html = render_template("certificate.html", **template_data)
        response_data = {
            "status": "success",
            "transaction": resp.data[0],
            "balance_after": new_balance,
            "receipt_url": receipt_url,
            "certificate_html": certificate_html
        }
        print(f"DEBUG API Response: {response_data}")  # Debug log
        return jsonify(response_data), 201
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

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

def get_member_by_customer_id(customer_id):
    resp = supabase.table("members").select("customer_id,name,phone,signature_url,photo_url").eq("customer_id", customer_id).execute()
    return resp.data[0] if resp.data else None

def get_staff_by_email(email):
    resp = supabase.table("staff").select("email,name,photo_url,signature_url").eq("email", email).execute()
    return resp.data[0] if resp.data else None

@staff_api_bp.route('/dashboard-stats', methods=['GET'])
def staff_dashboard_stats():
    """
    Totals for staff dashboard cards:
    - total_customers: count of approved members (fallback: all members)
    - active_loans: count of loans with status in ['approved','disbursed','active'] (fallback: all loans)
    - total_balance: sum of members.balance (missing/None => 0)
    """
    try:
        # Total customers
        try:
            mresp = supabase.table('members').select('id', count='exact').eq('status', 'approved').execute()
            total_customers = int(mresp.count) if hasattr(mresp, 'count') and mresp.count is not None else (len(mresp.data) if getattr(mresp, 'data', None) else 0)
            # Fallback to all members if approved returns 0 but there are members
            if total_customers == 0:
                mall = supabase.table('members').select('id', count='exact').execute()
                total_customers = int(mall.count) if hasattr(mall, 'count') and mall.count is not None else (len(mall.data) if getattr(mall, 'data', None) else 0)
        except Exception:
            # very defensive: try a basic select
            mall = supabase.table('members').select('id').execute()
            total_customers = len(mall.data) if getattr(mall, 'data', None) else 0

        # Active loans
        active_statuses = ['approved', 'disbursed', 'active']
        try:
            lresp = supabase.table('loans').select('id,status').execute()
            rows = lresp.data if getattr(lresp, 'data', None) else []
            active_loans = sum(1 for r in rows if str(r.get('status') or '').lower() in active_statuses)
            # Fallback: if status column not present or all empty, count all loans
            if active_loans == 0 and rows:
                active_loans = len(rows)
        except Exception:
            active_loans = 0

        # Total balance
        try:
            bresp = supabase.table('members').select('balance').execute()
            total_balance = 0.0
            for row in (bresp.data or []):
                try:
                    total_balance += float(row.get('balance') or 0)
                except Exception:
                    continue
        except Exception:
            total_balance = 0.0

        return jsonify({
            'status': 'success',
            'total_customers': total_customers,
            'active_loans': active_loans,
            'total_balance': round(total_balance, 2)
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@staff_bp.route('/transaction/certificate/<stid>')
def transaction_certificate(stid):
    """
    View, print, or download a deposit/withdrawal transaction certificate by STID.
    Query param: action=view|download|print|json (default: view)
    """
    action = request.args.get('action', 'view')
    # Fetch transaction by STID
    tx_resp = supabase.table("transactions").select("*").eq("stid", stid).execute()
    if not tx_resp.data:
        return jsonify({"status": "error", "message": "Transaction not found"}), 404
    tx = tx_resp.data[0]

    # Fetch member
    member = get_member_by_customer_id(tx["customer_id"])

    # Society info
    society_name = os.environ.get("SOCIETY_NAME", "Kushtagi Taluk High School Employees Cooperative Society Ltd., Kushtagi-583277")
    taluk_name = os.environ.get("TALUK_NAME", "Kushtagi")
    district_name = os.environ.get("DISTRICT_NAME", "koppala")

    template_data = dict(
        transaction=tx,
        member=member,
        society_name=society_name,
        taluk_name=taluk_name,
        district_name=district_name,
        amount_words=amount_to_words(tx["amount"])
    )

    if action == "json":
        return jsonify({
            "status": "success",
            "transaction": tx,
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
        pisa.CreatePDF(html, dest=pdf)
        response = make_response(pdf.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename={stid}.pdf'
        return response
    elif action == "print":
        html += "<script>window.onload = function(){window.print();}</script>"
        return html
    else:
        return html

@staff_api_bp.route('/logout', methods=['GET'])
def staff_logout():
    """Logout staff (clears session) and redirect to auth login."""
    session.clear()
    return redirect(url_for('auth.login'))

@staff_bp.route('/dashboard')
@login_required
@role_required('staff')
def staff_dashboard():
    return render_template('staff_dashboard.html')

@staff_bp.route('/customer-details')
def staff_customer_details():
    return render_template('staff_customer_details.html')

@staff_bp.route('/transaction/check/<stid>')
def check_transaction(stid):
    """
    Return the rendered check_transaction.html for a given transaction STID.
    Used for staff dashboard transaction check section.
    """
    # Fetch transaction by STID
    tx_resp = supabase.table("transactions").select("*").eq("stid", stid).execute()
    if not tx_resp.data:
        return "<div class='text-red-600'>Transaction not found.</div>", 404
    tx = tx_resp.data[0]

    # Fetch member
    member = get_member_by_customer_id(tx["customer_id"])

    # Society info
    society_name = os.environ.get("SOCIETY_NAME", "Kushtagi Taluk High School Employees Cooperative Society Ltd., Kushtagi-583277")
    taluk_name = os.environ.get("TALUK_NAME", "Kushtagi")
    district_name = os.environ.get("DISTRICT_NAME", "koppala")

    template_data = dict(
        transaction=tx,
        member=member,
        society_name=society_name,
        taluk_name=taluk_name,
        district_name=district_name,
        amount_words=amount_to_words(tx["amount"]),
        society_logo_url="https://geqletipzwxokceydhmi.supabase.co/storage/v1/object/public/staff-add/society_logo.png"
    )

    html = render_template("check_transaction.html", **template_data)
    return html

@staff_api_bp.route('/fetch-account', methods=['GET'])
def fetch_account_member():
    """
    Fetch full member details by customer_id from members table.
    Returns all fields needed by staff dashboard customer info section.
    """
    customer_id = request.args.get('customer_id')
    if not customer_id:
        return jsonify({'status': 'error', 'message': 'Missing customer_id'}), 400
    resp = (
        supabase.table("members")
        .select(
            "name,kgid,phone,email,salary,organization_name,address,photo_url,signature_url,balance,customer_id,status"
        )
        .eq("customer_id", customer_id)
        .limit(1)
        .execute()
    )
    if not resp.data:
        return jsonify({'status': 'error', 'message': 'Account not found'}), 404
    m = resp.data[0]
    return jsonify({
        'status': 'success',
        'name': m.get('name'),
        'kgid': m.get('kgid'),
        'phone': m.get('phone'),
        'email': m.get('email'),
        'salary': m.get('salary'),
        'organization_name': m.get('organization_name'),
        'address': m.get('address'),
        'photo_url': m.get('photo_url'),
        'signature_url': m.get('signature_url'),
        'balance': m.get('balance'),
        'customer_id': m.get('customer_id'),
        'status': m.get('status')
    }), 200

@staff_api_bp.route('/send-update-otp', methods=['POST'])
def send_update_otp():
    data = request.get_json()
    email = data.get('email')
    if not email or not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return jsonify({'status': 'error', 'message': 'Invalid email'}), 400
    otp = str(uuid.uuid4().int)[-6:]
    try:
        # Update OTP for this member (do not change other fields)
        supabase.table("members").update({"otp": otp}).eq("email", email).execute()
        send_otp_email(email, otp)
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Failed to send OTP', 'error': str(e)}), 500
    return jsonify({'status': 'success', 'message': 'OTP sent'})

@staff_api_bp.route('/verify-update-otp', methods=['POST'])
def verify_update_otp():
    data = request.get_json()
    email = data.get('email')
    otp = data.get('otp')
    if not email or not otp:
        return jsonify({'status': 'error', 'message': 'Missing email or OTP'}), 400
    member_rows = supabase.table("members").select("otp").eq("email", email).execute()
    if not member_rows.data or not member_rows.data[0].get("otp"):
        return jsonify({'status': 'error', 'message': 'OTP not found for this email'}), 400
    stored_otp = member_rows.data[0]["otp"]
    if otp != stored_otp:
        return jsonify({'status': 'error', 'message': 'Invalid or expired OTP'}), 400
    return jsonify({'status': 'success'})

@staff_api_bp.route('/update-customer', methods=['POST'])
def update_customer():
    # Accepts multipart/form-data (for images)
    form = request.form
    files = request.files
    customer_id = form.get('customer_id')
    otp = form.get('otp')
    if not customer_id or not otp:
        return jsonify({'status': 'error', 'message': 'Missing customer_id or OTP'}), 400

    # Fetch member (single attempt)
    try:
        member_rows = supabase.table("members") \
            .select("email,otp") \
            .eq("customer_id", customer_id) \
            .limit(1) \
            .execute()
    except RemoteProtocolError:
        return jsonify({'status': 'error', 'message': 'Upstream connection issue. Retry later.'}), 500
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Unexpected fetch error: {e}'}), 500

    if not member_rows.data or not member_rows.data[0].get("email"):
        return jsonify({'status': 'error', 'message': 'Customer not found'}), 404
    stored_otp = member_rows.data[0].get('otp')
    if otp != stored_otp:
        return jsonify({'status': 'error', 'message': 'Invalid or expired OTP'}), 400

    # Map & collect update fields
    update_fields = {}
    field_map = {
        'name': 'name',
        'kgid': 'kgid',
        'phone': 'phone',
        'email': 'email',
        'salary': 'salary',
        'aadhar_no': 'aadhar_no',
        'aadhaar_card': 'aadhar_no',
        'pan_no': 'pan_no',
        'pan_card': 'pan_no',
        'organization_name': 'organization_name',
        'address': 'address'
    }
    for incoming_key, target_key in field_map.items():
        if incoming_key in form and form.get(incoming_key) != '':
            val = form.get(incoming_key)
            if target_key == 'salary':
                try:
                    val = float(val)
                except Exception:
                    return jsonify({'status': 'error', 'message': 'Invalid salary value'}), 400
            update_fields[target_key] = val

    # Images
    bucket = supabase.storage.from_(SUPABASE_BUCKET)
    if 'photo' in files and files['photo'] and files['photo'].filename:
        photo = files['photo']
        try:
            photo_filename = f"{uuid.uuid4().hex}_{secure_filename(photo.filename)}"
            photo_buffer = compress_image(photo)
            bucket.upload(photo_filename, photo_buffer.read())
            update_fields['photo_url'] = f"{STORAGE_PUBLIC_PATH}/{photo_filename}"
        except Exception as e:
            return jsonify({'status': 'error', 'message': 'Photo upload failed', 'error': str(e)}), 500
    if 'signature' in files and files['signature'] and files['signature'].filename:
        signature = files['signature']
        try:
            signature_filename = f"{uuid.uuid4().hex}_{secure_filename(signature.filename)}"
            signature_buffer = compress_image(signature)
            bucket.upload(signature_filename, signature_buffer.read())
            update_fields['signature_url'] = f"{STORAGE_PUBLIC_PATH}/{signature_filename}"
        except Exception as e:
            return jsonify({'status': 'error', 'message': 'Signature upload failed', 'error': str(e)}), 500

    if not update_fields:
        return jsonify({'status': 'error', 'message': 'No valid fields to update'}), 400

    # Update + clear OTP
    try:
        supabase.table("members").update(update_fields).eq("customer_id", customer_id).execute()
        supabase.table("members").update({"otp": None}).eq("customer_id", customer_id).execute()
    except RemoteProtocolError:
        return jsonify({'status': 'error', 'message': 'Upstream write issue. Retry later.'}), 500
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Failed to update customer', 'error': str(e)}), 500

    # Fetch updated record
    try:
        updated = supabase.table("members").select(
            "customer_id,name,kgid,phone,email,salary,aadhar_no,pan_no,organization_name,address,photo_url,signature_url,status,balance"
        ).eq("customer_id", customer_id).limit(1).execute()
        customer_obj = updated.data[0] if updated.data else {}
    except Exception as e:
        customer_obj = {}
        print(f"Post-update fetch failed: {e}")

    return jsonify({'status': 'success', 'customer': customer_obj})


@staff_api_bp.route('/list-blocked-members', methods=['GET'])
def list_blocked_members():
    """
    List all blocked member accounts for staff to unblock.
    """
    try:
        resp = supabase.table("members").select("name,email,phone,kgid,status,blocked").eq("blocked", True).execute()
        members = resp.data if hasattr(resp, 'data') and resp.data else []
        return jsonify({'status': 'success', 'members': members}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@staff_api_bp.route('/fd-customer-info', methods=['GET'])
def fd_customer_info():
    """
    Fetch basic customer info for FD by customer_id.
    Returns: {status, customer: {name, kgid, aadhar_no, pan_no, customer_id}}
    """
    customer_id = request.args.get('customer_id')
    if not customer_id:
        return jsonify({'status': 'error', 'message': 'Missing customer_id'}), 400
    resp = (
        supabase.table("members")
        .select("name,kgid,aadhar_no,pan_no,customer_id")
        .eq("customer_id", customer_id)
        .limit(1)
        .execute()
    )
    if not resp.data:
        return jsonify({'status': 'error', 'message': 'Account not found'}), 404
    m = resp.data[0]
    return jsonify({
        'status': 'success',
        'customer': {
            'name': m.get('name'),
            'kgid': m.get('kgid'),
            'aadhar_no': m.get('aadhar_no'),
            'pan_no': m.get('pan_no'),
            'customer_id': m.get('customer_id')
        }
    }), 200

@staff_api_bp.route('/fd-list', methods=['GET'])
def fd_list():
    """List FDs for member; expose bank fdid (fdid) primarily, include system_fdid for internal reference."""
    customer_id = request.args.get('customer_id')
    if not customer_id:
        return jsonify({'status': 'error', 'message': 'Missing customer_id'}), 400
    resp = supabase.table("fixed_deposits").select(
        "id,fdid,system_fdid,amount,deposit_date,tenure,interest_rate,status,approved_by,approved_at"
    ).eq("customer_id", customer_id).order("deposit_date", desc=True).execute()
    fds = resp.data or []
    # Ensure backward compatibility: if fdid is null, set fdid to system_fdid in response for display
    for fd in fds:
        if not fd.get('fdid'):
            fd['fdid'] = fd.get('system_fdid')
    return jsonify({'status': 'success', 'fds': fds}), 200

@staff_api_bp.route('/create-fd', methods=['POST'])
def create_fd():
    """Create FD. Input: customer_id, amount, deposit_date (YYYY-MM-DD), tenure (months), interest_rate, optional fdid (bank ID).
    Returns: status, fdid (bank or internal), system_fdid, fd record."""
    try:
        # Handle both JSON and form data
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form.to_dict()
        
        # Required fields (only what's shown in the form)
        required_fields = ['customer_id', 'amount', 'deposit_date', 'tenure', 'interest_rate']
        missing_fields = []
        
        for field in required_fields:
            if field not in data or not data[field]:
                missing_fields.append(field)
        
        if missing_fields:
            return jsonify({
                'status': 'error', 
                'message': f'Missing required fields: {", ".join(missing_fields)}'
            }), 400
        
        # Validate customer exists
        customer_check = supabase.table("members").select("customer_id").eq("customer_id", data['customer_id']).execute()
        if not customer_check.data:
            return jsonify({'status': 'error', 'message': 'Customer not found'}), 404
        
        # Validate numeric fields
        try:
            amount = float(data['amount'])
            tenure = int(data['tenure'])
            interest_rate = float(data['interest_rate'])
            
            if amount <= 0:
                return jsonify({'status': 'error', 'message': 'Amount must be greater than 0'}), 400
            if tenure <= 0:
                return jsonify({'status': 'error', 'message': 'Tenure must be greater than 0'}), 400
            if interest_rate < 0:
                return jsonify({'status': 'error', 'message': 'Interest rate cannot be negative'}), 400
                
        except (ValueError, TypeError):
            return jsonify({'status': 'error', 'message': 'Invalid numeric values provided'}), 400
        
        # Optional bank-provided fdid (new external ID)
        bank_fdid = data.get('fdid') or data.get('bank_fdid') or data.get('bankFdId')
        if bank_fdid:
            bank_fdid = str(bank_fdid).strip()
            if len(bank_fdid) > 50:
                return jsonify({'status': 'error', 'message': 'FD ID too long (max 50 chars)'}), 400
        # Generate internal system_fdid always
        system_fdid = generate_system_fdid()
        fd_data = {
            "system_fdid": system_fdid,
            "fdid": bank_fdid,  # may be null
            "customer_id": data['customer_id'],
            "amount": amount,
            "deposit_date": data['deposit_date'],
            "tenure": tenure,
            "interest_rate": interest_rate,
            "status": "pending"
        }
        
        # Insert into fixed_deposits table
        resp = supabase.table("fixed_deposits").insert(fd_data).execute()
        
        if resp.data and len(resp.data) > 0:
            fd_row = resp.data[0]
            public_fdid = fd_row.get('fdid') or fd_row.get('system_fdid')
            return jsonify({
                'status': 'success',
                'fdid': public_fdid,
                'system_fdid': fd_row.get('system_fdid'),
                'fd': fd_row,
                'message': 'Fixed Deposit created successfully'
            }), 201
        else:
            return jsonify({'status': 'error', 'message': 'Failed to create Fixed Deposit'}), 500
            
    except Exception as e:
        print(f"Error in create_fd: {str(e)}")
        return jsonify({'status': 'error', 'message': f'Server error: {str(e)}'}), 500

@staff_api_bp.route('/close-fd', methods=['POST'])
def close_fd():
    """Close an approved FD. Body: fdid (bank or system), closure_date (YYYY-MM-DD), optional withdrawal_id.
    Returns payout details."""
    try:
        data = request.get_json(force=True)
        fdid = data.get('fdid')
        closure_date = data.get('closure_date')
        withdrawal_id = (data.get('withdrawal_id') or '').strip() or None
        if not fdid or not closure_date:
            return jsonify({'status':'error','message':'fdid and closure_date required'}), 400
        # Fetch FD by bank id else system id
        fd_resp = supabase.table('fixed_deposits').select('*').eq('fdid', fdid).limit(1).execute()
        if not fd_resp.data:
            fd_resp = supabase.table('fixed_deposits').select('*').eq('system_fdid', fdid).limit(1).execute()
        if not fd_resp.data:
            return jsonify({'status':'error','message':'FD not found'}), 404
        fd = fd_resp.data[0]
        if fd.get('status') == 'closed':
            return jsonify({'status':'error','message':'FD already closed'}), 400
        if fd.get('status') != 'approved':
            return jsonify({'status':'error','message':'Only approved FDs can be closed'}), 400
        # Compute interest (simple) pro-rata based on actual days vs tenure months
        from datetime import datetime
        try:
            dep_date = datetime.strptime(fd['deposit_date'], '%Y-%m-%d')
            close_dt = datetime.strptime(closure_date, '%Y-%m-%d')
        except Exception:
            return jsonify({'status':'error','message':'Invalid date format'}), 400
        if close_dt < dep_date:
            return jsonify({'status':'error','message':'Closure date before deposit date'}), 400
        principal = float(fd.get('amount') or 0)
        rate = float(fd.get('interest_rate') or 0)
        tenure_m = int(fd.get('tenure') or 0)
        # Full tenure days approximation (30 * months)
        full_days = max(1, tenure_m * 30)
        actual_days = (close_dt - dep_date).days
        if actual_days > full_days:
            actual_days = full_days
        interest_full = principal * rate * tenure_m / (12 * 100)
        interest_prorata = interest_full * (actual_days / full_days)
        interest_prorata = round(interest_prorata, 2)
        payout_amount = round(principal + interest_prorata, 2)
        update_fields = {
            'status':'closed',
            'closed_at': closure_date,
            'payout_interest': interest_prorata,
            'payout_amount': payout_amount,
            'withdrawal_id': withdrawal_id
        }
        upd = supabase.table('fixed_deposits').update(update_fields).eq('id', fd['id']).execute()
        # Email user (if member email exists)
        try:
            member_resp = supabase.table('members').select('email,name,customer_id').eq('customer_id', fd['customer_id']).limit(1).execute()
            if member_resp.data:
                member = member_resp.data[0]
                from app.notification.email_utils import send_email, _resolve_base_url
                base = _resolve_base_url() if '_resolve_base_url' in globals() else (os.getenv('PUBLIC_BASE_URL') or os.getenv('BASE_URL') or 'https://ksthstsociety.com')
                cert_link = f"{base}/fd/certificate/{fd.get('fdid') or fd.get('system_fdid')}?action=view"
                body = f"<p>Dear {member.get('name','Member')},</p><p>Your Fixed Deposit (FD ID: <strong>{fd.get('fdid') or fd.get('system_fdid')}</strong>) has been closed on {closure_date}.</p><ul><li>Principal: ₹{principal}</li><li>Interest Paid: ₹{interest_prorata}</li><li>Total Payout: ₹{payout_amount}</li></ul><p>Certificate Link: <a href='{cert_link}'>{cert_link}</a></p><p>Thank you.</p>"
                send_email(member.get('email'), f"FD Closed - {fd.get('fdid') or fd.get('system_fdid')}", body)
        except Exception as mail_err:
            print('FD close email error', mail_err)
        cert_url = f"{base}/fd/certificate/{fd.get('fdid') or fd.get('system_fdid')}?action=view"
        return jsonify({
            'status':'success',
            'fdid': fd.get('fdid') or fd.get('system_fdid'),
            'principal': principal,
            'payout_interest': interest_prorata,
            'payout_amount': payout_amount,
            'certificate_url': cert_url
        }), 200
    except Exception as e:
        print('close_fd error', e)
        return jsonify({'status':'error','message':f'Internal error: {e}'}), 500




