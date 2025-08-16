import os
import uuid
import re
import random
from flask import Blueprint, request, jsonify, render_template, make_response, abort, session
from werkzeug.utils import secure_filename
from io import BytesIO
from supabase import create_client, Client
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from PIL import Image
from datetime import datetime
import pdfkit
import inflect

staff_api_bp = Blueprint('staff_api', __name__, url_prefix='/staff/api')
staff_bp = Blueprint('staff', __name__, url_prefix='/staff')

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
    msg = MIMEText(f"Your OTP for staff registration is: {otp}")
    msg['Subject'] = "Staff Registration OTP"
    msg['From'] = EMAIL_USER
    msg['To'] = email
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.send_message(msg)
    except smtplib.SMTPException as e:
        raise RuntimeError(f"SMTP error: {e}")

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

def generate_customer_id(prefix="ABCDE"):
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

@staff_api_bp.route('/add-member', methods=['POST'])
def add_member():
    photo = request.files.get('photo')
    signature = request.files.get('signature')

    # Strip whitespace from form and file keys
    form = {k.strip(): v for k, v in request.form.items()}
    files = {k.strip(): v for k, v in request.files.items()}
    required_fields = ['name', 'phone', 'email', 'aadhar_no', 'pan_no', 'salary', 'organization_name', 'address', 'otp']
    data = {field: form.get(field, '').strip() for field in required_fields}
    # Handle kgid as optional
    kgid = form.get('kgid', '').strip()
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

    # Validate file type (basic check)
    allowed_types = {'image/jpeg', 'image/png', 'image/jpg'}
    if photo.mimetype not in allowed_types:
        return jsonify({'status': 'error', 'message': 'Photo must be a JPEG or PNG image'}), 400
    if signature.mimetype not in allowed_types:
        return jsonify({'status': 'error', 'message': 'Signature must be a JPEG or PNG image'}), 400

    # Optionally check file size (e.g., max 2MB)
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

    # Prepare member_data
    member_data = {
        "name": data['name'],
        "kgid": kgid,  # kgid is now optional
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

    # Generate customer_id if not already present
    customer_id = member_rows.data[0].get("customer_id") if member_rows.data and "customer_id" in member_rows.data[0] else None
    if not customer_id:
        # Ensure uniqueness (very unlikely to collide, but check anyway)
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
        # Always return customer_id in response
        member_data['customer_id'] = insert_resp.data[0].get('customer_id', customer_id)
        # Send pending email
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

@staff_api_bp.route('/add-transaction', methods=['POST'])
def add_transaction():
    required_fields = [
        "customer_id", "type", "amount",
        "from_account", "to_account", "date", "transaction_id"
    ]
    data = {field: request.form.get(field) for field in required_fields}
    missing = [f for f, v in data.items() if not v]
    if missing:
        return jsonify({'status': 'error', 'message': f'Missing fields: {", ".join(missing)}'}), 400

    # Optional remarks
    data["remarks"] = request.form.get("remarks", "")

    # Get current balance from members table using customer_id
    customer_id = data["customer_id"]
    member_row = supabase.table("members").select("balance").eq("customer_id", customer_id).execute()
    if not member_row.data or "balance" not in member_row.data[0]:
        return jsonify({"status": "error", "message": "Member not found or missing balance column. Please add 'balance' column to members table."}), 404
    current_balance = member_row.data[0]["balance"] or 0

    # Calculate new balance
    try:
        amount = float(data["amount"])
    except Exception:
        return jsonify({"status": "error", "message": "Invalid amount"}), 400

    if data["type"] == "deposit":
        new_balance = current_balance + amount
    elif data["type"] == "withdraw":
        new_balance = current_balance - amount
    else:
        return jsonify({"status": "error", "message": "Invalid transaction type"}), 400

    # Add balance_after to transaction data
    data["balance_after"] = new_balance

    # Generate unique stid for this transaction
    try:
        data["stid"] = generate_stid()
    except Exception as e:
        return jsonify({"status": "error", "message": f"Failed to generate STID: {e}"}), 500

    # Insert transaction
    try:
        resp = supabase.table("transactions").insert(data).execute()
        if not resp.data:
            raise Exception("Insert failed")
        # Update member's balance using customer_id
        supabase.table("members").update({"balance": new_balance}).eq("customer_id", customer_id).execute()
        return jsonify({"status": "success", "transaction": resp.data[0], "balance_after": new_balance}), 201
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

def amount_to_words(amount):
    try:
        n = int(float(amount))
        words = p.number_to_words(n, andword='').replace(',', '')
        return words.title() + " Rupees Only"
    except Exception:
        return str(amount)

def get_member_by_customer_id(customer_id):
    resp = supabase.table("members").select("customer_id,name,phone,signature_url,photo_url").eq("customer_id", customer_id).execute()
    return resp.data[0] if resp.data else None

def get_staff_by_email(email):
    resp = supabase.table("staff").select("email,name,photo_url,signature_url").eq("email", email).execute()
    return resp.data[0] if resp.data else None

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

    # Fetch staff from session
    staff_email = session.get("staff_email")
    staff = get_staff_by_email(staff_email) if staff_email else {}

    # Society info
    society_name = os.environ.get("SOCIETY_NAME", "Kushtagi Taluk High School Employees Cooperative Society Ltd., Kushtagi-583277")
    taluk_name = os.environ.get("TALUK_NAME", "Kushtagi")
    district_name = os.environ.get("DISTRICT_NAME", "koppala")

    template_data = dict(
        transaction=tx,
        member=member,
        staff=staff,
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
    else:
        return html

