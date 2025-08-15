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

def send_application_email(customer_email, loan_data):
    html_body = render_template("application_email.html", loan=loan_data)
    send_email(customer_email, "Loan Application Submitted", html_body)

def send_rejection_email(customer_email, loan_data, rejection_reason):
    html_body = render_template("rejection_email.html", loan=loan_data, reason=rejection_reason)
    send_email(customer_email, "Loan Application Rejected", html_body)

def send_approval_email_with_certificate(customer_email, loan_data, pdf_bytes):
    html_body = render_template("approval_email.html", loan=loan_data)
    send_email(customer_email, "Loan Approved - Certificate Attached", html_body, attachments=[(f"{loan_data['loan_id']}.pdf", pdf_bytes)])
