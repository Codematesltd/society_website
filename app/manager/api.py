import os
import uuid
import re
from flask import Blueprint, request, jsonify, current_app, session
from werkzeug.utils import secure_filename
from io import BytesIO
from supabase import create_client, Client
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from PIL import Image  # add back PIL import

manager_bp = Blueprint('manager', __name__, url_prefix='/manager')

# load .env into os.environ as early as possible
load_dotenv()

# Supabase config
SUPABASE_URL = os.environ.get("SUPABASE_URL")        # e.g. https://xyzcompany.supabase.co
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
SUPABASE_BUCKET = "staff-add"

# Public storage base
STORAGE_PUBLIC_PATH = f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_BUCKET}"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

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
    except smtplib.SMTPAuthenticationError:
        raise RuntimeError("SMTP Authentication failed: check EMAIL_USER/PASSWORD")
    except smtplib.SMTPException as e:
        raise RuntimeError(f"SMTP error occurred: {e}")

@manager_bp.route('/add-staff/send-otp', methods=['POST'])
def send_staff_otp():
    email = request.form.get('email')
    if not email or not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return jsonify({'status': 'error', 'message': 'Invalid email'}), 400
    otp = str(uuid.uuid4().int)[-6:]
    try:
        # Upsert staff row with email and OTP (other fields can be null/empty for now)
        supabase.table("staff").upsert({
            "email": email,
            "otp": otp
        }, on_conflict=["email"]).execute()
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

@manager_bp.route('/add-staff', methods=['POST'])
def add_staff():
    # Validate required fields
    required_fields = ['name', 'kgid', 'phone', 'email', 'aadhar_no', 'pan_no', 'organization_name', 'address', 'otp']
    data = {field: request.form.get(field, '').strip() for field in required_fields}
    missing = [f for f, v in data.items() if not v]
    if missing:
        return jsonify({'status': 'error', 'message': f'Missing fields: {", ".join(missing)}'}), 400

    # Email format
    if not re.match(r"[^@]+@[^@]+\.[^@]+", data['email']):
        return jsonify({'status': 'error', 'message': 'Invalid email format'}), 400

    # OTP check
    otp = data['otp']
    # Fetch staff row by email
    staff_rows = supabase.table("staff").select("otp").eq("email", data['email']).execute()
    if not staff_rows.data or not staff_rows.data[0].get("otp"):
        return jsonify({'status': 'error', 'message': 'OTP not found for this email'}), 400
    stored_otp = staff_rows.data[0]["otp"]
    if otp != stored_otp:
        return jsonify({'status': 'error', 'message': 'Invalid or expired OTP'}), 400
    # Optionally: clear OTP after use (set to NULL)
    supabase.table("staff").update({"otp": None}).eq("email", data['email']).execute()

    # File validation (just check presence)
    photo = request.files.get('photo')
    signature = request.files.get('signature')
    if not photo:
        return jsonify({'status': 'error', 'message': 'Missing photo file'}), 400
    if not signature:
        return jsonify({'status': 'error', 'message': 'Missing signature file'}), 400

    # Unique filenames
    photo_filename = f"{uuid.uuid4().hex}_{secure_filename(photo.filename)}"
    signature_filename = f"{uuid.uuid4().hex}_{secure_filename(signature.filename)}"

    # Compress images before upload
    try:
        photo_buffer = compress_image(photo)
        signature_buffer = compress_image(signature)
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Image processing failed', 'error': str(e)}), 400

    # Upload to Supabase Storage - with compression, no mimetype
    try:
        bucket = supabase.storage.from_(SUPABASE_BUCKET)
        bucket.upload(photo_filename, photo_buffer.read())
        bucket.upload(signature_filename, signature_buffer.read())
        photo_url = f"{STORAGE_PUBLIC_PATH}/{photo_filename}"
        signature_url = f"{STORAGE_PUBLIC_PATH}/{signature_filename}"
    except Exception as e:
        return jsonify({
            'status': 'error', 
            'message': 'Image upload failed',
            'error': str(e)
        }), 500

    # Prepare staff data for upsert
    staff_data = {
        "name": data['name'],
        "kgid": data['kgid'],
        "phone": data['phone'],
        "email": data['email'],
        "aadhar_no": data['aadhar_no'],
        "pan_no": data['pan_no'],
        "organization_name": data['organization_name'],
        "address": data['address'],
        "photo_url": photo_url,
        "signature_url": signature_url
    }

    # Insert or update staff data into Supabase table (upsert by email)
    try:
        # Use upsert with email as the conflict target
        insert_resp = supabase.table("staff").upsert(
            staff_data,
            on_conflict="email"  # reference the unique constraint
        ).execute()
        
        # Check if we got data back in the response
        if not insert_resp.data or len(insert_resp.data) == 0:
            raise Exception("Failed to insert/update staff record")
            
        # Get the inserted/updated record's ID
        staff_data['id'] = insert_resp.data[0]['id']
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': 'Database insert failed',
            'error': str(e)
        }), 500

    return jsonify({
        'status': 'success',
        'staff': staff_data
    }, 201)

def send_status_email(email, status):
    EMAIL_USER = os.getenv("EMAIL_USER")
    EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
    if not EMAIL_USER or not EMAIL_PASSWORD:
        raise RuntimeError("EMAIL_USER and EMAIL_PASSWORD must be set in environment")
    if status == "approved":
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

@manager_bp.route('/approve-member', methods=['POST'])
def approve_member():
    email = request.form.get('email')
    if not email:
        return jsonify({'status': 'error', 'message': 'Email required'}), 400
    try:
        resp = supabase.table("members").update({"status": "approved"}).eq("email", email).execute()
        if not resp.data or len(resp.data) == 0:
            return jsonify({'status': 'error', 'message': 'Member not found'}), 404
        send_status_email(email, "approved")
        return jsonify({'status': 'success', 'message': 'Member approved'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Failed to approve member', 'error': str(e)}), 500

@manager_bp.route('/reject-member', methods=['POST'])
def reject_member():
    email = request.form.get('email')
    if not email:
        return jsonify({'status': 'error', 'message': 'Email required'}), 400
    try:
        resp = supabase.table("members").update({"status": "rejected"}).eq("email", email).execute()
        if not resp.data or len(resp.data) == 0:
            return jsonify({'status': 'error', 'message': 'Member not found'}), 404
        send_status_email(email, "rejected")
        return jsonify({'status': 'success', 'message': 'Member rejected'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Failed to reject member', 'error': str(e)}), 500

@manager_bp.route('/unblock-member', methods=['POST'])
def unblock_member():
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

@manager_bp.route('/unblock-staff', methods=['POST'])
def unblock_staff():
    email = request.form.get('email')
    if not email:
        return jsonify({'status': 'error', 'message': 'Email required'}), 400
    try:
        resp = supabase.table("staff").update({"blocked": False, "login_attempts": 0}).eq("email", email).execute()
        if not resp.data or len(resp.data) == 0:
            return jsonify({'status': 'error', 'message': 'Staff not found'}), 404
        return jsonify({'status': 'success', 'message': 'Staff account unblocked'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Failed to unblock staff', 'error': str(e)}), 500

@manager_bp.route('/loan-applications', methods=['GET'])
def view_loan_applications():
    """
    View all pending loan applications.
    """
    try:
        loans = supabase.table("loans").select("*").eq("status", "pending").execute()
        return jsonify({'status': 'success', 'loans': loans.data}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Failed to fetch loan applications', 'error': str(e)}), 500

@manager_bp.route('/loan-application/<loan_id>', methods=['GET'])
def view_loan_application(loan_id):
    """
    View details of a specific loan application, including sureties and staff.
    """
    try:
        loan = supabase.table("loans").select("*").eq("id", loan_id).execute()
        if not loan.data:
            return jsonify({'status': 'error', 'message': 'Loan not found'}), 404
        sureties = supabase.table("sureties").select("*").eq("loan_id", loan_id).execute()
        staff = {
            "email": loan.data[0].get("staff_email"),
            "name": loan.data[0].get("staff_name"),
            "photo_url": loan.data[0].get("staff_photo_url"),
            "signature_url": loan.data[0].get("staff_signature_url")
        }
        return jsonify({
            'status': 'success',
            'loan': loan.data[0],
            'sureties': sureties.data,
            'staff': staff
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Failed to fetch loan application', 'error': str(e)}), 500

@manager_bp.route('/loan-application/approve/<loan_id>', methods=['POST'])
def approve_loan_application(loan_id):
    """
    Approve a pending loan application.
    """
    try:
        # Generate unique loan_id (LNXXXX)
        def generate_loan_id():
            resp = supabase.table("loans").select("loan_id").like("loan_id", "LN%").order("loan_id", desc=True).limit(1).execute()
            if resp.data and resp.data[0].get("loan_id"):
                last = resp.data[0]["loan_id"]
                match = re.match(r"LN(\d{4})", last)
                seq = int(match.group(1)) + 1 if match else 1
            else:
                seq = 1
            return f"LN{seq:04d}"

        unique_loan_id = generate_loan_id()
        resp = supabase.table("loans").update({"status": "approved", "loan_id": unique_loan_id}).eq("id", loan_id).execute()
        if not resp.data:
            return jsonify({'status': 'error', 'message': 'Loan not found or update failed'}), 404
        supabase.table("sureties").update({"active": True}).eq("loan_id", loan_id).execute()
        supabase.table("loan_records").insert({
            "loan_id": unique_loan_id,
            "outstanding_balance": resp.data[0]["loan_amount"],
            "status": "active"
        }).execute()
        return jsonify({'status': 'success', 'loan_id': unique_loan_id}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Failed to approve loan', 'error': str(e)}), 500

@manager_bp.route('/loan-application/reject/<loan_id>', methods=['POST'])
def reject_loan_application(loan_id):
    """
    Reject a pending loan application.
    """
    reason = request.json.get("reason")
    if not reason:
        return jsonify({'status': 'error', 'message': 'Rejection reason required'}), 400
    try:
        resp = supabase.table("loans").update({"status": "rejected", "rejection_reason": reason}).eq("id", loan_id).execute()
        if not resp.data:
            return jsonify({'status': 'error', 'message': 'Loan not found or update failed'}), 404
        supabase.table("sureties").update({"active": False}).eq("loan_id", loan_id).execute()
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Failed to reject loan', 'error': str(e)}), 500