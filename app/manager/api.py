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
    required_fields = ['name', 'kgid', 'phone', 'email', 'pan_aadhar', 'organization_name', 'address', 'otp']
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
        "pan_aadhar": data['pan_aadhar'],
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
    }), 201