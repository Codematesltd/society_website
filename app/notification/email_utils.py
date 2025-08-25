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

def _build_certificate_url(loan_data):
    """Return an absolute URL to view the loan certificate for this loan.
    Falls back to UUID if textual loan_id isn't available.
    """
    base = os.getenv("BASE_URL", "http://127.0.0.1:5000")
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
