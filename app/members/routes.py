from flask import render_template, request, jsonify, session, send_file, make_response
from werkzeug.security import check_password_hash
from app.auth.routes import supabase
from . import members_bp
from app.auth.decorators import login_required, role_required
from datetime import datetime, timedelta
import io
import pdfkit
import shutil
from math import floor  # optional for maturity calc

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
    API to fetch member account overview with extended fields.
    """
    user_email = session.get("email")
    if not user_email:
        return jsonify({"status": "error", "message": "Not logged in"}), 401

    member_resp = supabase.table("members").select(
        "name,kgid,phone,email,address,customer_id,organization_name,photo_url,signature_url,aadhar_no,pan_no,balance,share_amount,salary,created_at"
    ).eq("email", user_email).limit(1).execute()
    if not member_resp.data:
        return jsonify({"status": "error", "message": "Member not found"}), 404

    m = member_resp.data[0]
    # Optional: normalize key names for frontend consistency
    m["aadhaar"] = m.get("aadhar_no")
    m["pan"] = m.get("pan_no")
    return jsonify({"status": "success", "data": m}), 200

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
    member_resp = supabase.table("members").select("customer_id,balance").eq("email", user_email).execute()
    if not member_resp.data:
        return jsonify({"status": "error", "message": "Member not found"}), 404
    customer_id = member_resp.data[0]["customer_id"]
    current_balance = float(member_resp.data[0].get("balance") or 0)

    # Parse query params
    range_type = request.args.get("range", "last10")
    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")

    now = datetime.now()
    date_col = "date"  # transactions use 'date' column

    # Helper to fetch transactions according to range
    txs = []
    try:
        if range_type == "last10":
            tx_resp = supabase.table("transactions").select("*").eq("customer_id", customer_id).order(date_col, desc=True).limit(20).execute()
        elif range_type == "1m":
            since = (now - timedelta(days=30)).strftime("%Y-%m-%d")
            tx_resp = supabase.table("transactions").select("*").eq("customer_id", customer_id).gte(date_col, since).order(date_col, desc=True).execute()
        elif range_type == "3m":
            since = (now - timedelta(days=90)).strftime("%Y-%m-%d")
            tx_resp = supabase.table("transactions").select("*").eq("customer_id", customer_id).gte(date_col, since).order(date_col, desc=True).execute()
        elif range_type == "6m":
            since = (now - timedelta(days=180)).strftime("%Y-%m-%d")
            tx_resp = supabase.table("transactions").select("*").eq("customer_id", customer_id).gte(date_col, since).order(date_col, desc=True).execute()
        elif range_type == "1y":
            since = (now - timedelta(days=365)).strftime("%Y-%m-%d")
            tx_resp = supabase.table("transactions").select("*").eq("customer_id", customer_id).gte(date_col, since).order(date_col, desc=True).execute()
        elif range_type == "custom":
            if not from_date or not to_date:
                return jsonify({"status": "error", "message": "from_date and to_date required for custom range"}), 400
            try:
                datetime.strptime(from_date, "%Y-%m-%d")
                datetime.strptime(to_date, "%Y-%m-%d")
            except Exception:
                return jsonify({"status": "error", "message": "Invalid date format"}), 400
            tx_resp = supabase.table("transactions").select("*").eq("customer_id", customer_id).gte(date_col, from_date).lte(date_col, to_date).order(date_col, desc=True).execute()
        else:
            return jsonify({"status": "error", "message": "Invalid range type"}), 400

        txs = tx_resp.data if tx_resp.data else []
    except Exception:
        txs = []

    # Helper to fetch approved loans (treated as deposit events) in same range
    loans = []
    try:
        created_col = "created_at"
        if range_type == "last10":
            loans_resp = supabase.table("loans").select("*").eq("customer_id", customer_id).eq("status", "approved").order(created_col, desc=True).limit(20).execute()
        elif range_type in ("1m", "3m", "6m", "1y"):
            # derive since from range_type above
            if range_type == "1m":
                since = (now - timedelta(days=30)).strftime("%Y-%m-%d")
            elif range_type == "3m":
                since = (now - timedelta(days=90)).strftime("%Y-%m-%d")
            elif range_type == "6m":
                since = (now - timedelta(days=180)).strftime("%Y-%m-%d")
            else:
                since = (now - timedelta(days=365)).strftime("%Y-%m-%d")
            loans_resp = supabase.table("loans").select("*").eq("customer_id", customer_id).eq("status", "approved").gte(created_col, since).order(created_col, desc=True).execute()
        else:  # custom
            loans_resp = supabase.table("loans").select("*").eq("customer_id", customer_id).eq("status", "approved").gte(created_col, from_date).lte(created_col, to_date).order(created_col, desc=True).execute()
        loans = loans_resp.data if loans_resp.data else []
    except Exception:
        loans = []

    # Normalize both lists into unified event objects
    events = []
    for t in txs:
        # tolerate different field names
        d = t.get(date_col) or t.get("transaction_date") or t.get("created_at") or ""
        amount = 0.0
        try:
            amount = float(t.get("amount") or 0)
        except Exception:
            amount = 0.0
        ev_type = str(t.get("type") or "").lower()
        events.append({
            "source": "transaction",
            "date": str(d),
            "type": ev_type,
            "amount": amount,
            "remarks": t.get("remarks") or t.get("description") or "",
            "stid": t.get("stid") or t.get("transaction_id") or t.get("id"),
        })

    for ln in loans:
        d = ln.get("created_at") or ""
        amt = 0.0
        try:
            amt = float(ln.get("loan_amount") or 0)
        except Exception:
            amt = 0.0
        events.append({
            "source": "loan",
            "date": str(d),
            "type": "deposit",
            "amount": amt,
            "remarks": f"Loan disbursement (Loan ID: {ln.get('loan_id') or ln.get('id')})",
            "stid": ln.get("loan_id") or ln.get("id")
        })

    # Sort by date desc (newest first). Use ISO string ordering; fallback to empty strings.
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

    return jsonify({"status": "success", "transactions": events}), 200

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
        transactions = result.data or []

        # --- NEW: fetch approved loans in same range and merge as deposit events ---
        try:
            # reuse same period logic above: range_type, from_date, to_date, now, customer_id, etc.
            loan_query = supabase.table("loans").select("*").eq("customer_id", customer_id).eq("status","approved")
            if range_type == "last10":
                loan_query = loan_query.order("created_at", desc=True).limit(10)
            elif range_type in ("1m","3m","6m","1y"):
                # derive since as before...
                if range_type == "1m":
                    since = (now - timedelta(days=30)).strftime("%Y-%m-%d")
                elif range_type == "3m":
                    since = (now - timedelta(days=90)).strftime("%Y-%m-%d")
                elif range_type == "6m":
                    since = (now - timedelta(days=180)).strftime("%Y-%m-%d")
                else:
                    since = (now - timedelta(days=365)).strftime("%Y-%m-%d")
                loan_query = loan_query.gte("created_at", since).order("created_at", desc=True)
            else:  # custom
                loan_query = loan_query.gte("created_at", from_date).lte("created_at", to_date).order("created_at", desc=True)
            loan_res = loan_query.execute()
            for ln in loan_res.data or []:
                transactions.append({
                    "date": ln.get("created_at") or "",
                    "stid": ln.get("loan_id"),
                    "type": "deposit",
                    "amount": float(ln.get("loan_amount") or 0),
                    "remarks": f"Loan disbursement (Loan ID: {ln.get('loan_id')})",
                })
        except Exception:
            pass

        # resort combined list by date desc
        transactions.sort(key=lambda t: t.get("date",""), reverse=True)

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
    """Fetch a member's single loan and its repayment records (enhanced).

    Query params:
      loan_id: required (e.g. LN0001)

    Enhancements vs. previous version:
      * Includes loan created_at (if present) so UI can show applied date.
      * Returns interest_amount & principal_amount for each repayment row (if columns exist).
      * Returns interest_amount from the summary row (repayment_amount is null) so UI can compute totals.
      * Gracefully handles absence of summary row or columns (falls back to empty / 0 values).
    """
    loan_id = request.args.get("loan_id")
    if not loan_id:
        return jsonify({"status": "error", "message": "loan_id is required"}), 400

    try:
        # Fetch loan details (add created_at for UI if available)
        loan_resp = supabase.table("loans").select(
            "loan_id,customer_id,loan_type,loan_amount,interest_rate,loan_term_months,purpose_of_loan,purpose_of_emergency_loan,status,created_at"
        ).eq("loan_id", loan_id).limit(1).execute()
        if not loan_resp.data:
            return jsonify({"status": "error", "message": "Loan not found"}), 404
        loan = loan_resp.data[0]

        # Purpose normalization
        purpose = loan.get("purpose_of_loan") or loan.get("purpose_of_emergency_loan") or "-"

        # Fetch repayment records (attempt extended columns; fall back gracefully)
        # We request potential columns; Supabase will ignore non-existent but safer to catch exceptions
        record_columns = "repayment_date,repayment_amount,outstanding_balance,status,interest_amount,principal_amount"
        records_resp = supabase.table("loan_records").select(record_columns).eq("loan_id", loan_id).order("repayment_date", desc=False).execute()
        records = records_resp.data or []

        # Identify summary row (repayment_amount is null) if present
        summary = None
        for r in records:
            if r.get("repayment_amount") is None:
                summary = r
                break

        # Optional: compute aggregate if summary missing (basic fallback)
        if not summary:
            # Derive outstanding as last outstanding_balance value (if any)
            if records:
                try:
                    last_outstanding = [r for r in records if r.get("outstanding_balance") is not None]
                    last_outstanding = last_outstanding[-1]["outstanding_balance"] if last_outstanding else 0
                except Exception:
                    last_outstanding = 0
            else:
                last_outstanding = 0
            summary = {
                "repayment_amount": None,
                "outstanding_balance": last_outstanding,
                "interest_amount": None,  # Unknown without summary row
                "status": loan.get("status") or "active"
            }
            records.append(summary)  # append so frontend can still treat similarly

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
                "created_at": loan.get("created_at"),
            },
            "records": records
        }), 200
    except Exception as e:
        print(f"[ERROR] /api/loan-details failed for loan_id={loan_id}: {e}")
        return jsonify({"status": "error", "message": "Failed to fetch loan details"}), 500

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

@members_bp.route("/api/my-fds", methods=["GET"])
@login_required
@role_required('members')
def api_my_fds():
    """
    Return all fixed deposits for the logged-in member with simple maturity info.
    """
    user_email = session.get("email")
    if not user_email:
        return jsonify({"status": "error", "message": "Not logged in"}), 401
    # Get customer_id
    member_resp = supabase.table("members").select("customer_id").eq("email", user_email).limit(1).execute()
    if not member_resp.data:
        return jsonify({"status": "error", "message": "Member not found"}), 404
    customer_id = member_resp.data[0]["customer_id"]

    fd_resp = supabase.table("fixed_deposits").select(
        "fdid,amount,deposit_date,tenure,interest_rate,status,approved_at"
    ).eq("customer_id", customer_id).order("deposit_date", desc=True).execute()
    fds = fd_resp.data or []

    # Add quick maturity amount calc (simple interest)
    enriched = []
    for fd in fds:
        try:
            principal = float(fd.get("amount") or 0)
            rate = float(fd.get("interest_rate") or 0)
            tenure_m = int(fd.get("tenure") or 0)
            interest = round(principal * rate * tenure_m / (12 * 100), 2)
            maturity_amount = round(principal + interest, 2)
        except Exception:
            interest = 0.0
            maturity_amount = fd.get("amount")
        fd["maturity_amount"] = maturity_amount
        enriched.append(fd)

    return jsonify({"status": "success", "fds": enriched}), 200