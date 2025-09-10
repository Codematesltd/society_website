import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from flask import render_template
from dotenv import load_dotenv

load_dotenv()

EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

def send_email(to_email, subject, html_body, attachments=None):
    msg = MIMEMultipart()
    msg['From'] = EMAIL_USER
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(html_body, 'html'))
    if attachments:
        for filename, filebytes in attachments:
            part = MIMEApplication(filebytes, Name=filename)
            part['Content-Disposition'] = f'attachment; filename="{filename}"'
            msg.attach(part)
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        # Log error (print for now)
        print(f"Email send error: {e}")

def _resolve_base_url():
    """Determine absolute base URL for emails (loan/FD)."""
    return (os.getenv("PUBLIC_BASE_URL") or os.getenv("BASE_URL") or "https://ksthstsociety.com").rstrip('/')

def _build_certificate_url(loan_data):
    """Return loan certificate URL (prefers textual loan_id)."""
    base = _resolve_base_url()
    # prefer textual loan_id like LN0001, else use id (UUID)
    loan_id = None
    if isinstance(loan_data, dict):
        loan_id = loan_data.get("loan_id") or loan_data.get("id")
    if not loan_id:
        return None
    return f"{base}/loan/certificate/{loan_id}?action=view"

def send_application_email(customer_email, loan_data):
    # Render template and append certificate link for convenience
    html_body = render_template("application_email.html", loan=loan_data)
    cert_url = _build_certificate_url(loan_data)
    if cert_url:
        html_body += f"<hr><p>You can view your application details and certificate here: <a href=\"{cert_url}\">{cert_url}</a></p>"
    send_email(customer_email, "Loan Application Submitted", html_body)

def send_rejection_email(customer_email, loan_data, rejection_reason):
    html_body = render_template("rejection_email.html", loan=loan_data, reason=rejection_reason)
    send_email(customer_email, "Loan Application Rejected", html_body)

def send_approval_email_with_certificate(customer_email, loan_data, pdf_bytes):
    html_body = render_template("approval_email.html", loan=loan_data)
    cert_url = _build_certificate_url(loan_data)
    if cert_url:
        html_body += f"<hr><p>View your loan certificate online: <a href=\"{cert_url}\">{cert_url}</a></p>"
    # Keep attaching the PDF as before, but also provide a web link
    loan_id_display = (loan_data or {}).get('loan_id') or (loan_data or {}).get('id') or 'loan'
    send_email(
        customer_email,
        "Loan Approved - Certificate Attached",
        html_body,
        attachments=[(f"{loan_id_display}.pdf", pdf_bytes)] if pdf_bytes else None
    )

def _normalized_base():
    return _resolve_base_url()

def _build_fd_certificate_url(fd_data):
    base = _normalized_base()
    if not fd_data:
        return None
    # Bank-provided FDID preferred; fallback to internal system_fdid then numeric id
    fdid = fd_data.get("fdid") or fd_data.get("system_fdid") or fd_data.get("id")
    if not fdid:
        return None
    return f"{base}/fd/certificate/{fdid}?action=view"

def send_fd_approval_email(customer_email, customer_name, fd_data):
    if not customer_email:
        return
    cert_url = _build_fd_certificate_url(fd_data)
    fdid = (fd_data or {}).get('fdid') or (fd_data or {}).get('system_fdid', 'FD')
    amount = (fd_data or {}).get('amount')
    tenure = (fd_data or {}).get('tenure')
    rate = (fd_data or {}).get('interest_rate')
    html_body = f"""
        <p>Dear {customer_name},</p>
        <p>Your Fixed Deposit (FDID: <strong>{fdid}</strong>) has been approved.</p>
        <ul>
          <li>Amount: ₹{amount}</li>
          <li>Tenure: {tenure} months</li>
          <li>Interest Rate: {rate}%</li>
        </ul>
        <p>You can view / download your FD certificate here:<br>
        <a href="{cert_url}">{cert_url}</a></p>
        <p>Thank you.</p>
    """
    send_email(customer_email, f"FD Approved - {fdid}", html_body)
