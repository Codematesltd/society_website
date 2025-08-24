from flask import render_template, request, jsonify, session, send_file, make_response
from werkzeug.security import check_password_hash
from app.auth.routes import supabase
from . import members_bp
from app.auth.decorators import login_required, role_required
from datetime import datetime, timedelta
import io
import pdfkit
import shutil

@members_bp.route("/dashboard")
@login_required
@role_required('members')
def dashboard():
    return render_template('user_dashboard.html')

@members_bp.route("/api/check-balance", methods=["POST"])
def api_check_balance():
    """
    API to check member balance after verifying password.
    Expects JSON: { "password": "plain_password" }
    Returns: { "status": "success", "balance": amount } or error message.
    """
    user_email = session.get("email")
    if not user_email:
        return jsonify({"status": "error", "message": "Not logged in"}), 401

    data = request.get_json(silent=True) or {}
    password = data.get("password")
    if not password:
        return jsonify({"status": "error", "message": "Password required"}), 400

    # Fetch member by email
    member_resp = supabase.table("members").select("password,balance").eq("email", user_email).execute()
    if not member_resp.data:
        return jsonify({"status": "error", "message": "Member not found"}), 404

    member = member_resp.data[0]
    hashed_pw = member.get("password")
    if not hashed_pw or not check_password_hash(hashed_pw, password):
        return jsonify({"status": "error", "message": "Incorrect password"}), 403

    balance = member.get("balance", 0)
    return jsonify({"status": "success", "balance": balance}), 200

@members_bp.route("/api/account-overview", methods=["GET"])
def api_account_overview():
    """
    API to fetch member account overview.
    Returns: { "status": "success", "data": { name, kgid, phone, email, address, customer_id, organization_name, photo_url } }
    """
    user_email = session.get("email")
    if not user_email:
        return jsonify({"status": "error", "message": "Not logged in"}), 401

    member_resp = supabase.table("members").select(
        "name,kgid,phone,email,address,customer_id,organization_name,photo_url"
    ).eq("email", user_email).execute()
    if not member_resp.data:
        return jsonify({"status": "error", "message": "Member not found"}), 404

    member = member_resp.data[0]
    return jsonify({"status": "success", "data": member}), 200

@members_bp.route("/api/statements", methods=["GET"])
def api_statements():
    """
    API to fetch member statements.
    Query params:
      - range: 'last10' (default), '1m', '3m', '6m', '1y', 'custom'
      - from_date: (YYYY-MM-DD, required if range=custom)
      - to_date: (YYYY-MM-DD, required if range=custom)
    Returns: { "status": "success", "transactions": [...] }
    """
    user_email = session.get("email")
    if not user_email:
        return jsonify({"status": "error", "message": "Not logged in"}), 401

    # Get customer_id for the logged-in user
    member_resp = supabase.table("members").select("customer_id").eq("email", user_email).execute()
    if not member_resp.data:
        return jsonify({"status": "error", "message": "Member not found"}), 404
    customer_id = member_resp.data[0]["customer_id"]

    # Parse query params
    range_type = request.args.get("range", "last10")
    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")

    # Use the correct column name for date (likely 'date' instead of 'transaction_date')
    query = supabase.table("transactions").select("*").eq("customer_id", customer_id)

    now = datetime.now()
    date_col = "date"  # Change this to your actual date column name in the transactions table

    if range_type == "last10":
        query = query.order(date_col, desc=True).limit(10)
    elif range_type == "1m":
        since = (now - timedelta(days=30)).strftime("%Y-%m-%d")
        query = query.gte(date_col, since).order(date_col, desc=True)
    elif range_type == "3m":
        since = (now - timedelta(days=90)).strftime("%Y-%m-%d")
        query = query.gte(date_col, since).order(date_col, desc=True)
    elif range_type == "6m":
        since = (now - timedelta(days=180)).strftime("%Y-%m-%d")
        query = query.gte(date_col, since).order(date_col, desc=True)
    elif range_type == "1y":
        since = (now - timedelta(days=365)).strftime("%Y-%m-%d")
        query = query.gte(date_col, since).order(date_col, desc=True)
    elif range_type == "custom":
        if not from_date or not to_date:
            return jsonify({"status": "error", "message": "from_date and to_date required for custom range"}), 400
        try:
            from_dt = datetime.strptime(from_date, "%Y-%m-%d")
            to_dt = datetime.strptime(to_date, "%Y-%m-%d")
        except Exception:
            return jsonify({"status": "error", "message": "Invalid date format"}), 400
        query = query.gte(date_col, from_date).lte(date_col, to_date).order(date_col, desc=True)
    else:
        return jsonify({"status": "error", "message": "Invalid range type"}), 400

    result = query.execute()
    transactions = result.data if result.data else []

    return jsonify({"status": "success", "transactions": transactions}), 200

@members_bp.route("/api/download-statement", methods=["GET"])
def download_statement():
    """
    Download account statement as PDF.
    Query params: same as /api/statements
    """
    try:
        user_email = session.get("email")
        if not user_email:
            return "Not logged in", 401

        # Fetch member info
        member_resp = supabase.table("members").select(
            "name,kgid,phone,email,address,customer_id,organization_name,photo_url,balance"
        ).eq("email", user_email).execute()
        if not member_resp.data:
            return "Member not found", 404
        member = member_resp.data[0]

        # Get transactions using same logic as api_statements
        range_type = request.args.get("range", "last10")
        from_date = request.args.get("from_date")
        to_date = request.args.get("to_date")
        customer_id = member["customer_id"]
        query = supabase.table("transactions").select("*").eq("customer_id", customer_id)
        now = datetime.now()
        date_col = "date"
        if range_type == "last10":
            query = query.order(date_col, desc=True).limit(10)
            period_text = "Last 10 Transactions"
        elif range_type == "1m":
            since = (now - timedelta(days=30)).strftime("%Y-%m-%d")
            query = query.gte(date_col, since).order(date_col, desc=True)
            period_text = "Last 1 Month"
        elif range_type == "3m":
            since = (now - timedelta(days=90)).strftime("%Y-%m-%d")
            query = query.gte(date_col, since).order(date_col, desc=True)
            period_text = "Last 3 Months"
        elif range_type == "6m":
            since = (now - timedelta(days=180)).strftime("%Y-%m-%d")
            query = query.gte(date_col, since).order(date_col, desc=True)
            period_text = "Last 6 Months"
        elif range_type == "1y":
            since = (now - timedelta(days=365)).strftime("%Y-%m-%d")
            query = query.gte(date_col, since).order(date_col, desc=True)
            period_text = "Last 1 Year"
        elif range_type == "custom":
            if not from_date or not to_date:
                return "from_date and to_date required for custom range", 400
            try:
                from_dt = datetime.strptime(from_date, "%Y-%m-%d")
                to_dt = datetime.strptime(to_date, "%Y-%m-%d")
            except Exception:
                return "Invalid date format", 400
            query = query.gte(date_col, from_date).lte(date_col, to_date).order(date_col, desc=True)
            period_text = f"{from_date} to {to_date}"
        else:
            return "Invalid range type", 400

        result = query.execute()
        transactions = result.data if result.data else []

        html_content = render_template(
            "statement.html",
            name=member.get("name"),
            customer_id=member.get("customer_id"),
            address=member.get("address"),
            org_name=member.get("organization_name"),
            photo_url=member.get("photo_url"),
            period_text=period_text,
            transactions=transactions,
            generated_on=datetime.now().strftime("%Y-%m-%d %H:%M"),
            kgid=member.get("kgid"),
            email=member.get("email"),
            phone=member.get("phone")
        )

        # Pure Python PDF generation using xhtml2pdf (no external binaries required)
        try:
            from xhtml2pdf import pisa
            pdf_io = io.BytesIO()
            pisa_status = pisa.CreatePDF(html_content, dest=pdf_io)
            if pisa_status.err:
                raise Exception("xhtml2pdf failed to generate PDF")
            pdf_io.seek(0)
            response = make_response(pdf_io.read())
            response.headers['Content-Type'] = 'application/pdf'
            response.headers['Content-Disposition'] = f'attachment; filename=statement_{datetime.now().strftime("%Y%m%d")}.pdf'
            return response
        except Exception as e:
            print(f"PDF generation error: {str(e)}")
            return render_template(
                "statement.html",
                name=member.get("name"),
                customer_id=member.get("customer_id"),
                address=member.get("address"),
                org_name=member.get("organization_name"),
                photo_url=member.get("photo_url"),
                period_text=period_text,
                transactions=transactions,
                generated_on=datetime.now().strftime("%Y-%m-%d %H:%M"),
                kgid=member.get("kgid"),
                email=member.get("email"),
                phone=member.get("phone"),
                error_message="PDF generation failed. Please use your browser's Print > Save as PDF."
            ), 200

    except Exception as e:
        print(f"Statement download error: {str(e)}")
        return f"Error generating statement: {str(e)}", 500

@members_bp.route("/api/loan-details", methods=["GET"])
def api_loan_details():
    """
    API to fetch loan details for a given loan_id.
    Query params:
      - loan_id: required
    Returns: {
      "status": "success",
      "loan": {loan_id, customer_id, loan_type, loan_amount, interest_rate, loan_term_months, purpose, status},
      "records": [ ...repayment records... ]
    }
    """
    loan_id = request.args.get("loan_id")
    if not loan_id:
        return jsonify({"status": "error", "message": "loan_id is required"}), 400

    # Fetch loan details from loans table
    loan_resp = supabase.table("loans").select(
        "loan_id,customer_id,loan_type,loan_amount,interest_rate,loan_term_months,purpose_of_loan,purpose_of_emergency_loan,status"
    ).eq("loan_id", loan_id).limit(1).execute()
    if not loan_resp.data:
        return jsonify({"status": "error", "message": "Loan not found"}), 404

    loan = loan_resp.data[0]
    # Prefer purpose_of_loan, fallback to purpose_of_emergency_loan
    purpose = loan.get("purpose_of_loan") or loan.get("purpose_of_emergency_loan") or "-"

    # Fetch repayment records from loan_records table
    records_resp = supabase.table("loan_records").select(
        "repayment_date,repayment_amount,outstanding_balance,status"
    ).eq("loan_id", loan_id).order("repayment_date", desc=False).execute()
    records = records_resp.data if records_resp.data else []

    return jsonify({
        "status": "success",
        "loan": {
            "loan_id": loan.get("loan_id"),
            "customer_id": loan.get("customer_id"),
            "loan_type": loan.get("loan_type"),
            "loan_amount": loan.get("loan_amount"),
            "interest_rate": loan.get("interest_rate"),
            "loan_term_months": loan.get("loan_term_months"),
            "purpose": purpose,
            "status": loan.get("status"),
        },
        "records": records
    }), 200

@members_bp.route("/api/my-loans", methods=["GET"])
def api_my_loans():
    """
    API to fetch all loans for the logged-in user (by customer_id).
    Returns: { "status": "success", "loans": [ ... ] }
    """
    user_email = session.get("email")
    if not user_email:
        return jsonify({"status": "error", "message": "Not logged in"}), 401

    # Get customer_id for the logged-in user
    member_resp = supabase.table("members").select("customer_id").eq("email", user_email).execute()
    if not member_resp.data:
        return jsonify({"status": "error", "message": "Member not found"}), 404
    customer_id = member_resp.data[0]["customer_id"]

    # Fetch all loans for this customer_id
    loans_resp = supabase.table("loans").select(
        "loan_id,customer_id,loan_type,loan_amount,interest_rate,loan_term_months,purpose_of_loan,purpose_of_emergency_loan,status,rejection_reason"
    ).eq("customer_id", customer_id).order("created_at", desc=True).execute()
    loans = []
    for loan in loans_resp.data or []:
        purpose = loan.get("purpose_of_loan") or loan.get("purpose_of_emergency_loan") or "-"
        loans.append({
            "loan_id": loan.get("loan_id"),
            "customer_id": loan.get("customer_id"),
            "loan_type": loan.get("loan_type"),
            "loan_amount": loan.get("loan_amount"),
            "interest_rate": loan.get("interest_rate"),
            "loan_term_months": loan.get("loan_term_months"),
            "purpose": purpose,
            "status": loan.get("status"),
            "rejection_reason": loan.get("rejection_reason"),
        })

    return jsonify({"status": "success", "loans": loans}), 200