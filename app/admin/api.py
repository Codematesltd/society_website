import os
from flask import Blueprint, request, jsonify, session

from supabase import create_client
from dotenv import load_dotenv
from datetime import datetime, timedelta


admin_api_bp = Blueprint('admin_api', __name__, url_prefix='/admin/api')

# Load environment variables
load_dotenv()

# Supabase setup
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
import pandas as pd
from io import BytesIO
from flask import make_response
# --- Excel Export Endpoints for Audit Sections ---
@admin_api_bp.route('/audit-summary/excel', methods=['GET'])
def audit_summary_excel():
    # Example: Export total credit, debit, expense as a single-row Excel
    credit_total = float(request.args.get('credit_total', 0))
    debit_total = float(request.args.get('debit_total', 0))
    expense_total = float(request.args.get('expense_total', 0))
    df = pd.DataFrame([{
        'Total Credit': credit_total,
        'Total Debit': debit_total,
        'Total Expense': expense_total
    }])
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Summary")
    output.seek(0)
    response = make_response(output.read())
    response.headers["Content-Disposition"] = "attachment; filename=audit_summary.xlsx"
    response.headers["Content-Type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return response

@admin_api_bp.route('/audit-transactions/excel', methods=['GET'])
def audit_transactions_excel():
    """
    Export all transactions data to Excel.
    """
    try:
        resp = supabase.table('transactions').select('*').execute()
        txs = resp.data if hasattr(resp, 'data') and resp.data else []
        df = pd.DataFrame(txs)
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Transactions")
        output.seek(0)
        response = make_response(output.read())
        response.headers["Content-Disposition"] = "attachment; filename=audit_transactions.xlsx"
        response.headers["Content-Type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        return response
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Failed to generate transactions Excel: {str(e)}'}), 500

@admin_api_bp.route('/audit-loans/excel', methods=['GET'])
def audit_loans_excel():
    """
    Export loans data to Excel with joined information from loans and loan_records tables.
    Returns: name, customerid, loan_id, loan_amount, interest_amount, principle_amount, remaining_principle_amount
    """
    try:
        # Get all loans with member details
        loans_resp = supabase.table('loans').select('*').execute()
        loans = loans_resp.data if hasattr(loans_resp, 'data') and loans_resp.data else []
        
        # Get all loan records
        loan_records_resp = supabase.table('loan_records').select('*').execute()
        loan_records = loan_records_resp.data if hasattr(loan_records_resp, 'data') and loan_records_resp.data else []
        
        # Get all members
        members_resp = supabase.table('members').select('*').execute()
        members = members_resp.data if hasattr(members_resp, 'data') and members_resp.data else []
        
        # Create lookup dictionaries
        member_lookup = {member['customer_id']: member for member in members}
        loan_records_lookup = {}
        for record in loan_records:
            loan_id = record.get('loan_id')
            if loan_id not in loan_records_lookup:
                loan_records_lookup[loan_id] = record
        
        # Build Excel data
        excel_data = []
        for loan in loans:
            customer_id = loan.get('customer_id')
            loan_id = loan.get('loan_id')
            member = member_lookup.get(customer_id, {})
            loan_record = loan_records_lookup.get(loan_id, {})
            
            excel_data.append({
                'Name': member.get('name', ''),
                'Customer ID': customer_id,
                'Loan ID': loan_id,
                'Loan Amount': loan.get('loan_amount', 0),
                'Interest Amount': loan_record.get('interest_amount', 0),
                'Principle Amount': loan_record.get('principle_amount', 0),
                'Remaining Principle Amount': loan_record.get('remaining_principle_amount', 0)
            })
        
        df = pd.DataFrame(excel_data)
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Loans")
        output.seek(0)
        
        response = make_response(output.read())
        response.headers["Content-Disposition"] = "attachment; filename=audit_loans.xlsx"
        response.headers["Content-Type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        return response
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Failed to generate loans Excel: {str(e)}'}), 500

@admin_api_bp.route('/audit-expenses/excel', methods=['GET'])
def audit_expenses_excel():
    """
    Export all expenses data to Excel.
    """
    try:
        resp = supabase.table('expenses').select('*').execute()
        expenses = resp.data if hasattr(resp, 'data') and resp.data else []
        df = pd.DataFrame(expenses)
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Expenses")
        output.seek(0)
        response = make_response(output.read())
        response.headers["Content-Disposition"] = "attachment; filename=audit_expenses.xlsx"
        response.headers["Content-Type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        return response
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Failed to generate expenses Excel: {str(e)}'}), 500

@admin_api_bp.route('/audit-salaries/excel', methods=['GET'])
def audit_salaries_excel():
    """
    Export all staff salaries data to Excel.
    """
    try:
        resp = supabase.table('staff_salaries').select('*').execute()
        salaries = resp.data if hasattr(resp, 'data') and resp.data else []
        df = pd.DataFrame(salaries)
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Salaries")
        output.seek(0)
        response = make_response(output.read())
        response.headers["Content-Disposition"] = "attachment; filename=audit_salaries.xlsx"
        response.headers["Content-Type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        return response
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Failed to generate salaries Excel: {str(e)}'}), 500

@admin_api_bp.route('/fd-yearly-summary', methods=['GET'])
def fd_yearly_summary():
    """
    Yearly summary of Fixed Deposits: total FD amount, interest paid, and active FDs.
    Query params (optional): year (defaults to current UTC year)
    Returns: { status, year, labels[Jan..Dec], fd_amounts[12], interest_paid[12], total_fd_amount, total_interest_paid, active_fds }
    """
    try:
        now = datetime.utcnow()
        year = int(request.args.get('year', now.year))
        
        # Date range for the year
        start_dt = datetime(year, 1, 1)
        end_dt = datetime(year + 1, 1, 1)
        start_str = start_dt.strftime('%Y-%m-%d')
        end_str = end_dt.strftime('%Y-%m-%d')
        
        # Initialize monthly arrays
        labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        fd_amounts = [0.0] * 12
        interest_paid = [0.0] * 12
        total_fd_amount = 0.0
        total_interest_paid = 0.0
        active_fds = 0
        
        # Fetch all FDs (for monthly stats, only those opened in the year; for active count, all FDs up to year end)
        resp = supabase.table('fixed_deposits') \
            .select('amount,deposit_date,payout_interest,status,closed_at') \
            .execute()
        fds = resp.data if hasattr(resp, 'data') and resp.data else []

        for fd in fds:
            try:
                # FD amount by month (only for FDs opened in the selected year)
                deposit_date = str(fd.get('deposit_date') or '')
                if deposit_date and len(deposit_date) >= 7:
                    deposit_year = int(deposit_date[:4])
                    if deposit_year == year:
                        month_idx = int(deposit_date[5:7]) - 1
                        if 0 <= month_idx < 12:
                            amount = float(fd.get('amount') or 0)
                            fd_amounts[month_idx] += amount
                            total_fd_amount += amount

                # Interest paid calculation (same as before)
                payout_interest = float(fd.get('payout_interest') or 0)
                if payout_interest > 0:
                    interest_date = str(fd.get('closed_at') or fd.get('deposit_date') or '')
                    if interest_date and len(interest_date) >= 7:
                        month_idx = int(interest_date[5:7]) - 1
                        if 0 <= month_idx < 12:
                            interest_paid[month_idx] += payout_interest
                            total_interest_paid += payout_interest

            except Exception:
                continue

        # Count Active FDs: status == 'active' only
        active_fds = 0
        for fd in fds:
            try:
                status = str(fd.get('status') or '').lower()
                if status == 'approved':
                    active_fds += 1
            except Exception:
                continue
        
        return jsonify({
            'status': 'success',
            'year': year,
            'labels': labels,
            'fd_amounts': [round(x, 2) for x in fd_amounts],
            'interest_paid': [round(x, 2) for x in interest_paid],
            'total_fd_amount': round(total_fd_amount, 2),
            'total_interest_paid': round(total_interest_paid, 2),
            'active_fds': active_fds
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@admin_api_bp.route('/audit-fd/excel', methods=['GET'])
def audit_fd_excel():
    """
    Export Fixed Deposits data to Excel.
    Returns: system_fdicustomer_id, amount, deposit_date, tenure, status, fdid(transaction_id), closed_at, payout_amount, withdrawal_id
    """
    try:
        resp = supabase.table('fixed_deposits').select('*').execute()
        fds = resp.data if hasattr(resp, 'data') and resp.data else []
        
        # Format data for Excel
        excel_data = []
        for fd in fds:
            excel_data.append({
                'System FD Customer ID': fd.get('customer_id', ''),
                'Amount': float(fd.get('amount') or 0),
                'Deposit Date': str(fd.get('deposit_date') or ''),
                'Tenure': fd.get('tenure', ''),
                'Status': fd.get('status', ''),
                'FD ID (Transaction ID)': fd.get('fdid', ''),
                'Closed At': str(fd.get('closed_at') or ''),
                'Payout Amount': float(fd.get('payout_amount') or 0),
                'Withdrawal ID': fd.get('withdrawal_id', '')
            })
        
        df = pd.DataFrame(excel_data)
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Fixed Deposits")
        output.seek(0)
        
        response = make_response(output.read())
        response.headers["Content-Disposition"] = "attachment; filename=audit_fixed_deposits.xlsx"
        response.headers["Content-Type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        return response
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Failed to generate FD Excel: {str(e)}'}), 500

@admin_api_bp.route('/share-amount-summary', methods=['GET'])
def share_amount_summary():
    """
    Share amount summary: total share amounts and member breakdown.
    Returns: { status, total_share_amount, member_count, members: [{ name, customer_id, share_amount }] }
    """
    try:
        # Fetch all members with share amounts
        resp = supabase.table('members') \
            .select('name,customer_id,share_amount') \
            .execute()
        members = resp.data if hasattr(resp, 'data') and resp.data else []
        
        total_share_amount = 0.0
        member_count = 0
        member_details = []
        
        for member in members:
            share_amount = float(member.get('share_amount') or 0)
            if share_amount > 0:  # Only include members with share amounts
                total_share_amount += share_amount
                member_count += 1
                member_details.append({
                    'name': member.get('name'),
                    'customer_id': member.get('customer_id'),
                    'share_amount': round(share_amount, 2)
                })
        
        return jsonify({
            'status': 'success',
            'total_share_amount': round(total_share_amount, 2),
            'member_count': member_count,
            'members': member_details
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@admin_api_bp.route('/share-amount/excel', methods=['GET'])
def share_amount_excel():
    """
    Export share amount data to Excel with Name, Customer ID, and Share Amount.
    """
    try:
        # Fetch members with share amounts
        resp = supabase.table('members') \
            .select('name,customer_id,share_amount') \
            .execute()
        members = resp.data if hasattr(resp, 'data') and resp.data else []
        
        # Filter and format data for Excel
        excel_data = []
        for member in members:
            share_amount = float(member.get('share_amount') or 0)
            if share_amount > 0:  # Only include members with share amounts
                excel_data.append({
                    'Name': member.get('name') or '',
                    'Customer ID': member.get('customer_id') or '',
                    'Share Amount': share_amount
                })
        
        df = pd.DataFrame(excel_data)
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Share Amounts")
        output.seek(0)
        
        response = make_response(output.read())
        response.headers["Content-Disposition"] = "attachment; filename=share_amounts.xlsx"
        response.headers["Content-Type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        return response
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@admin_api_bp.route('/loan-info', methods=['GET'])
def loan_info():
    """
    Get loan info by loan_id only.
    Query params: loan_id (required)
    Returns: Name, loan_amount, loan_term_months, interest_rate, next_installment_amount, outstanding_amount
    """
    loan_id = request.args.get('loan_id')
    if not loan_id:
        return jsonify({'status': 'error', 'message': 'loan_id is required'}), 400
    try:
        # Fetch loan by loan_id
        loan_query = supabase.table("loans").select("*").filter("loan_id", "eq", loan_id)
        loan_resp = loan_query.limit(1).execute()
        if not loan_resp.data or len(loan_resp.data) == 0:
            return jsonify({'status': 'error', 'message': 'Loan not found'}), 404
        loan = loan_resp.data[0]
        # Fetch member name and photo_url
        member_resp = supabase.table("members").select("name,photo_url").filter("customer_id", "eq", loan["customer_id"]).limit(1).execute()
        name = member_resp.data[0]["name"] if member_resp.data and len(member_resp.data) > 0 else None
        photo_url = member_resp.data[0]["photo_url"] if member_resp.data and len(member_resp.data) > 0 else None
        # Fetch loan records and compute outstanding + EMI-based next installment
        records_resp = supabase.table("loan_records") \
            .select("repayment_date,repayment_amount,outstanding_balance") \
            .filter("loan_id", "eq", loan["loan_id"]) \
            .order("repayment_date") \
            .execute()
        records = records_resp.data if hasattr(records_resp, 'data') and records_resp.data else []

        # Determine latest known outstanding balance
        outstanding_amount = None
        for rec in reversed(records):
            if rec.get('outstanding_balance') is not None:
                try:
                    outstanding_amount = float(rec.get('outstanding_balance') or 0)
                except Exception:
                    outstanding_amount = None
                break
        if outstanding_amount is None:
            # Fallback: if no records, assume full principal still outstanding
            try:
                outstanding_amount = float(loan.get('loan_amount') or 0)
            except Exception:
                outstanding_amount = 0.0

        # Compute EMI from loan terms (monthly reducing balance)
        try:
            P = float(loan.get('loan_amount') or 0)
            n = int(loan.get('loan_term_months') or 0)
            annual_rate = float(loan.get('interest_rate') or 0)
        except Exception:
            P, n, annual_rate = 0.0, 0, 0.0
        r = (annual_rate / 100.0) / 12.0 if annual_rate and n else 0.0
        if P > 0 and n > 0:
            if r > 0:
                try:
                    pow_term = (1 + r) ** n
                    emi = P * r * pow_term / (pow_term - 1)
                except Exception:
                    emi = P / n
            else:
                emi = P / n
        else:
            emi = 0.0

        # Next installment should be the EMI, capped by remaining outstanding (last installment may be smaller)
        next_installment = min(emi, outstanding_amount) if outstanding_amount > 0 and emi > 0 else (0.0 if outstanding_amount <= 0 else outstanding_amount)
        result = {
            'name': name,
            'loan_amount': loan.get('loan_amount'),
            'loan_term_months': loan.get('loan_term_months'),
            'interest_rate': loan.get('interest_rate'),
            'next_installment_amount': round(float(next_installment or 0), 2),
            'outstanding_amount': round(float(outstanding_amount or 0), 2),
            'photo_url': photo_url
        }
        return jsonify({'status': 'success', 'loan_info': result}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@admin_api_bp.route('/monthly-summary', methods=['GET'])
def monthly_summary():
    """
    Return total deposits and withdrawals for a given month, plus daily series for charts.
    Query params (optional): year, month (1-12). Defaults to current UTC year/month.
    Response: {
      status: 'success', year, month,
      total_deposit, total_withdrawal,
      labels: [1..N], deposits: [..], withdrawals: [..]
    }
    """
    try:
        now = datetime.utcnow()
        year = int(request.args.get('year', now.year))
        month = int(request.args.get('month', now.month))
        if month < 1 or month > 12:
            return jsonify({'status': 'error', 'message': 'month must be 1-12'}), 400

        # Compute month range [start, next_month)
        start_dt = datetime(year, month, 1)
        if month == 12:
            next_dt = datetime(year + 1, 1, 1)
        else:
            next_dt = datetime(year, month + 1, 1)
        start_str = start_dt.strftime('%Y-%m-%d')
        end_str = next_dt.strftime('%Y-%m-%d')

        # Fetch transactions within month
        resp = supabase.table('transactions') \
            .select('type,amount,date') \
            .gte('date', start_str) \
            .lt('date', end_str) \
            .execute()
        txs = resp.data if hasattr(resp, 'data') and resp.data else []

        # Aggregate totals and per-day series
        days_in_month = (next_dt - start_dt).days
        labels = list(range(1, days_in_month + 1))
        deposits = [0.0 for _ in labels]
        withdrawals = [0.0 for _ in labels]
        total_deposit = 0.0
        total_withdrawal = 0.0

        for tx in txs:
            try:
                amt = float(tx.get('amount') or 0)
            except Exception:
                # Skip rows with non-numeric amount
                continue
            tx_type = str(tx.get('type') or '').lower()
            # Extract day from date string (supports 'YYYY-MM-DD' or ISO datetime)
            dstr = str(tx.get('date') or '')[:10]
            try:
                day = int(dstr.split('-')[2])
            except Exception:
                continue
            idx = day - 1
            if 0 <= idx < len(labels):
                if tx_type == 'deposit':
                    deposits[idx] += amt
                    total_deposit += amt
                elif tx_type in ('withdraw', 'withdrawal'):
                    withdrawals[idx] += amt
                    total_withdrawal += amt

        # Round for neatness
        deposits = [round(x, 2) for x in deposits]
        withdrawals = [round(x, 2) for x in withdrawals]

        return jsonify({
            'status': 'success',
            'year': year,
            'month': month,
            'total_deposit': round(total_deposit, 2),
            'total_withdrawal': round(total_withdrawal, 2),
            'labels': labels,
            'deposits': deposits,
            'withdrawals': withdrawals
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@admin_api_bp.route('/loan-yearly-summary', methods=['GET'])
def loan_yearly_summary():
    """
    Yearly summary for loans: how much was disbursed (loan amounts) vs recovered (repayments).
    Query params (optional): year. Defaults to current UTC year.
    Response: {
      status: 'success', year,
      total_disbursed, total_recovered,
      labels: ['Jan',...,'Dec'], disbursed: [12], recovered: [12]
    }
    """
    try:
        now = datetime.utcnow()
        year = int(request.args.get('year', now.year))

        # Compute year range [start, next_year)
        start_dt = datetime(year, 1, 1)
        next_dt = datetime(year + 1, 1, 1)
        start_str = start_dt.strftime('%Y-%m-%d')
        end_str = next_dt.strftime('%Y-%m-%d')

        # Labels for 12 months
        labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        disbursed = [0.0] * 12
        recovered = [0.0] * 12
        total_disbursed = 0.0
        total_recovered = 0.0

        # Fetch loans created within the year (treat as disbursed when approved)
        loan_resp = supabase.table('loans') \
            .select('loan_amount,created_at,status') \
            .gte('created_at', start_str) \
            .lt('created_at', end_str) \
            .execute()
        loans = loan_resp.data if hasattr(loan_resp, 'data') and loan_resp.data else []
        
        for loan in loans:
            try:
                amt = float(loan.get('loan_amount') or 0)
            except Exception:
                amt = 0.0
            if amt <= 0:
                continue
                
            created = str(loan.get('created_at') or '')[:10]
            try:
                month_idx = int(created.split('-')[1]) - 1
            except Exception:
                continue
                
            # Only count approved loans as disbursed
            status = str(loan.get('status') or '').lower()
            if status in ('approved', 'completed', 'active'):
                if 0 <= month_idx < 12:
                    disbursed[month_idx] += amt
                    total_disbursed += amt

        # Fetch repayments within the year (from loan_records)
        rec_resp = supabase.table('loan_records') \
            .select('repayment_amount,repayment_date') \
            .gte('repayment_date', start_str) \
            .lt('repayment_date', end_str) \
            .execute()
        recs = rec_resp.data if hasattr(rec_resp, 'data') and rec_resp.data else []
        
        for rec in recs:
            try:
                amt = float(rec.get('repayment_amount') or 0)
            except Exception:
                amt = 0.0
            if amt <= 0:
                continue
            d = str(rec.get('repayment_date') or '')[:10]
            try:
                month_idx = int(d.split('-')[1]) - 1
            except Exception:
                continue
            if 0 <= month_idx < 12:
                recovered[month_idx] += amt
                total_recovered += amt

        # Round values
        disbursed = [round(x, 2) for x in disbursed]
        recovered = [round(x, 2) for x in recovered]

        return jsonify({
            'status': 'success',
            'year': year,
            'total_disbursed': round(total_disbursed, 2),
            'total_recovered': round(total_recovered, 2),
            'labels': labels,
            'disbursed': disbursed,
            'recovered': recovered
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@admin_api_bp.route('/staff-salary-yearly-summary', methods=['GET'])
def staff_salary_yearly_summary():
    """
    Yearly summary of staff salaries paid.
    Query params (optional): year (defaults to current UTC year)
    Returns: { status, year, labels[Jan..Dec], totals[12], total_year }
    """
    try:
        now = datetime.utcnow()
        year = int(request.args.get('year', now.year))
        start_dt = datetime(year, 1, 1)
        next_dt = datetime(year + 1, 1, 1)
        start_str = start_dt.strftime('%Y-%m-%d')
        end_str = next_dt.strftime('%Y-%m-%d')

        labels = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
        totals = [0.0] * 12
        total_year = 0.0

        resp = supabase.table('staff_salaries') \
            .select('salary,date') \
            .gte('date', start_str) \
            .lt('date', end_str) \
            .execute()
        rows = resp.data if hasattr(resp, 'data') and resp.data else []
        for r in rows:
            try:
                amt = float(r.get('salary') or 0)
            except Exception:
                amt = 0.0
            d = str(r.get('date') or '')[:10]
            try:
                midx = int(d.split('-')[1]) - 1
            except Exception:
                continue
            if 0 <= midx < 12:
                totals[midx] += amt
                total_year += amt

        totals = [round(x, 2) for x in totals]
        return jsonify({'status': 'success', 'year': year, 'labels': labels, 'totals': totals, 'total_year': round(total_year, 2)}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@admin_api_bp.route('/staff-salary-monthly-summary', methods=['GET'])
def staff_salary_monthly_summary():
    """
    Monthly summary of staff salaries by day for a given month.
    Query params (optional): year, month (1-12) defaults to current UTC.
    Returns: { status, year, month, labels[1..N], totals[], total_month }
    """
    try:
        now = datetime.utcnow()
        year = int(request.args.get('year', now.year))
        month = int(request.args.get('month', now.month))
        if month < 1 or month > 12:
            return jsonify({'status': 'error', 'message': 'month must be 1-12'}), 400
        start_dt = datetime(year, month, 1)
        next_dt = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
        start_str = start_dt.strftime('%Y-%m-%d')
        end_str = next_dt.strftime('%Y-%m-%d')
        days = (next_dt - start_dt).days
        labels = list(range(1, days + 1))
        totals = [0.0] * days
        total_month = 0.0

        resp = supabase.table('staff_salaries') \
            .select('salary,date') \
            .gte('date', start_str) \
            .lt('date', end_str) \
            .execute()
        rows = resp.data if hasattr(resp, 'data') and resp.data else []
        for r in rows:
            try:
                amt = float(r.get('salary') or 0)
            except Exception:
                amt = 0.0
            d = str(r.get('date') or '')[:10]
            try:
                day = int(d.split('-')[2])
            except Exception:
                continue
            idx = day - 1
            if 0 <= idx < len(totals):
                totals[idx] += amt
                total_month += amt

        totals = [round(x, 2) for x in totals]
        return jsonify({'status': 'success', 'year': year, 'month': month, 'labels': labels, 'totals': totals, 'total_month': round(total_month, 2)}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@admin_api_bp.route('/expenses-monthly-summary', methods=['GET'])
def expenses_monthly_summary():
    """
    Monthly summary of expenses by day.
    Query params (optional): year, month (1-12) defaults to current UTC.
    Returns: { status, year, month, labels[1..N], totals[], total_month }
    """
    try:
        now = datetime.utcnow()
        year = int(request.args.get('year', now.year))
        month = int(request.args.get('month', now.month))
        if month < 1 or month > 12:
            return jsonify({'status': 'error', 'message': 'month must be 1-12'}), 400
        start_dt = datetime(year, month, 1)
        next_dt = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
        start_str = start_dt.strftime('%Y-%m-%d')
        end_str = next_dt.strftime('%Y-%m-%d')
        days = (next_dt - start_dt).days
        labels = list(range(1, days + 1))
        totals = [0.0] * days
        total_month = 0.0

        # Use Supabase client directly to query 'expenses'
        resp = supabase.table('expenses') \
            .select('amount,date') \
            .gte('date', start_str) \
            .lt('date', end_str) \
            .execute()
        rows = resp.data if hasattr(resp, 'data') and resp.data else []
        for r in rows:
            try:
                amt = float(r.get('amount') or 0)
            except Exception:
                amt = 0.0
            d = str(r.get('date') or '')[:10]
            try:
                day = int(d.split('-')[2])
            except Exception:
                continue
            idx = day - 1
            if 0 <= idx < len(totals):
                totals[idx] += amt
                total_month += amt

        totals = [round(x, 2) for x in totals]
        return jsonify({'status': 'success', 'year': year, 'month': month, 'labels': labels, 'totals': totals, 'total_month': round(total_month, 2)}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@admin_api_bp.route('/total-amount-summary', methods=['GET'])
def total_amount_summary():
    """
    Overall totals: total user balance (members.balance) + share_amount (members.share_amount) + interest earned from loan_records.interest_amount.
    Returns: { status, total_balance, total_share_amount, total_interest_earned, total_amount }
    """
    try:
        # Sum balances and share amounts from members
        mresp = supabase.table('members').select('balance,share_amount').execute()
        members_data = mresp.data if hasattr(mresp, 'data') and mresp.data else []
        total_balance = 0.0
        total_share_amount = 0.0
        for row in members_data:
            try:
                total_balance += float(row.get('balance') or 0)
                total_share_amount += float(row.get('share_amount') or 0)
            except Exception:
                continue

        # Sum interest from loan_records using interest_amount column specifically
        lresp = supabase.table('loan_records').select('interest_amount').execute()
        lrows = lresp.data if hasattr(lresp, 'data') and lresp.data else []
        total_interest = 0.0
        for r in lrows:
            try:
                interest_val = float(r.get('interest_amount') or 0)
                if interest_val > 0:
                    total_interest += interest_val
            except Exception:
                continue

        # Total amount includes balance + share amount + interest earned
        total_amount = total_balance + total_share_amount + total_interest

        return jsonify({
            'status': 'success',
            'total_balance': round(total_balance, 2),
            'total_share_amount': round(total_share_amount, 2),
            'total_interest_earned': round(total_interest, 2),
            'total_amount': round(total_amount, 2)
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# List staff salaries with pagination
@admin_api_bp.route('/list-staff-salaries', methods=['GET'])
def list_staff_salaries():
    """
    List staff salaries with pagination. Query params: page, page_size
    """
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 10))
        offset = (page - 1) * page_size
        # Get total count
        total_resp = supabase.table("staff_salaries").select('id', count='exact').execute()
        total = getattr(total_resp, 'count', None)
        if total is None:
            # fallback for some supabase clients
            total = len(total_resp.data) if hasattr(total_resp, 'data') and total_resp.data else 0
        # Get paginated data, order by date desc, id desc
        resp = supabase.table("staff_salaries") \
            .select("name,kgid,salary,to_account,from_account,transaction_id,date") \
            .order("date", desc=True) \
            .order("id", desc=True) \
            .range(offset, offset + page_size - 1) \
            .execute()
        salaries = resp.data if hasattr(resp, 'data') and resp.data else []
        # Always return a list, never None
        if not isinstance(salaries, list):
            salaries = []
        return jsonify({
            'status': 'success',
            'salaries': salaries,
            'total': total
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@admin_api_bp.route('/account-requests', methods=['GET'])
def get_account_requests():
    """
    Get all pending account requests.
    """
    try:
        response = supabase.table("members") \
            .select("name,email,phone,kgid,created_at") \
            .eq("status", "pending") \
            .execute()
        
        return jsonify({
            'status': 'success',
            'members': response.data
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@admin_api_bp.route('/approve-member', methods=['POST'])
def approve_member():
    """
    Approve a pending account request.
    """
    email = request.form.get('email')
    if not email:
        return jsonify({
            'status': 'error',
            'message': 'Email is required'
        }), 400
    
    try:
        # Update member status to approved
        response = supabase.table("members") \
            .update({"status": "approved"}) \
            .eq("email", email) \
            .execute()
        
        if not response.data or len(response.data) == 0:
            return jsonify({
                'status': 'error',
                'message': 'Member not found'
            }), 404
        
        # Send approval email
        try:
            # Try to import and use the send_status_email function
            from app.manager.api import send_status_email
            send_status_email(email, "approved")
        except Exception as e:
            # Continue even if email sending fails
            print(f"Error sending approval email: {e}")
            
        return jsonify({
            'status': 'success',
            'message': 'Member approved successfully'
        }, 200)
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@admin_api_bp.route('/reject-member', methods=['POST'])
def reject_member():
    """
    Reject a pending account request.
    """
    email = request.form.get('email')
    if not email:
        return jsonify({
            'status': 'error',
            'message': 'Email is required'
        }), 400
    
    try:
        # Update member status to rejected
        response = supabase.table("members") \
            .update({"status": "rejected"}) \
            .eq("email", email) \
            .execute()
        
        if not response.data or len(response.data) == 0:
            return jsonify({
                'status': 'error',
                'message': 'Member not found'
            }), 404
        
        # Send rejection email
        try:
            # Try to import and use the send_status_email function
            from app.manager.api import send_status_email
            send_status_email(email, "rejected")
        except Exception as e:
            # Continue even if email sending fails
            print(f"Error sending rejection email: {e}")
            
        return jsonify({
            'status': 'success',
            'message': 'Member rejected successfully'
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@admin_api_bp.route('/add-staff-salary', methods=['POST'])
def add_staff_salary():
    """
    Add a new staff salary record.
    Required fields: name, kgid, salary, to_account, from_account, transaction_id, date
    """
    data = request.get_json() or request.form
    required_fields = ["name", "kgid", "salary", "to_account", "from_account", "transaction_id", "date"]
    missing = [f for f in required_fields if not data.get(f)]
    if missing:
        return jsonify({
            'status': 'error',
            'message': f"Missing fields: {', '.join(missing)}"
        }), 400

    try:
        # Insert into staff_salaries table
        response = supabase.table("staff_salaries").insert({
            "name": data["name"],
            "kgid": data["kgid"],
            "salary": float(data["salary"]),
            "to_account": data["to_account"],
            "from_account": data["from_account"],
            "transaction_id": data["transaction_id"],
            "date": data["date"]
        }).execute()
        if response.data:
            return jsonify({
                'status': 'success',
                'message': 'Staff salary added successfully',
                'record': response.data[0]
            }), 201
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to add staff salary'
            }), 500
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@admin_api_bp.route('/member-details/<email>', methods=['GET'])
def member_details(email):
    """
    Get full member details by email only.
    """
    try:
        resp = supabase.table("members").select(
            "customer_id, name, kgid, email, phone, aadhar_no, pan_no, salary, organization_name, address, status, balance, created_at, photo_url, signature_url"
        ).eq("email", email).execute()
        
        if resp.data and len(resp.data) > 0:
            return jsonify({"status": "success", "member": resp.data[0]}), 200
        
        return jsonify({"status": "error", "message": "Member not found"}), 404
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@admin_api_bp.route('/customer-info', methods=['GET'])
def customer_info():
    """
    Get customer info by customer_id or kgid.
    Returns: name, kgid, customer_id, phone, email, organization_name, photo_url, signature_url from members,
             loan_amount, interest_rate, loan_tenure from loans,
             outstanding_amount from loan_records.
    """
    customer_id = request.args.get('customer_id')
    kgid = request.args.get('kgid')
    # Only allow search by customer_id for security and clarity
    if not customer_id:
        return jsonify({'status': 'error', 'message': 'customer_id required'}), 400
    try:
        # Fetch member (include balance and share_amount for admin view)
        member_query = supabase.table("members").select(
            "name,kgid,customer_id,phone,email,organization_name,photo_url,signature_url,balance,share_amount"
        ).eq("customer_id", customer_id)
        member_resp = member_query.limit(1).execute()
        if not member_resp.data or len(member_resp.data) == 0:
            return jsonify({'status': 'error', 'message': 'Member not found'}), 404
        member = member_resp.data[0]

        # Fetch loans for the member
        loans_resp = supabase.table("loans").select(
            "loan_id,loan_amount,interest_rate,loan_term_months,loan_type,status,created_at"
        ).eq("customer_id", member["customer_id"]).execute()
        loans = loans_resp.data if hasattr(loans_resp, 'data') else []

        # For each loan, fetch outstanding_amount from loan_records
        loan_list = []
        for loan in loans:
            records_resp = supabase.table("loan_records").select("outstanding_balance").eq("loan_id", loan["loan_id"]).order("repayment_date").execute()
            outstanding = None
            if records_resp.data and len(records_resp.data) > 0:
                # Get last non-null outstanding_balance
                for rec in reversed(records_resp.data):
                    if rec.get("outstanding_balance") is not None:
                        outstanding = rec["outstanding_balance"]
                        break
            if outstanding is None:
                outstanding = loan.get("loan_amount", 0)
            loan_list.append({
                "loan_id": loan.get("loan_id"),
                "loan_amount": loan.get("loan_amount"),
                "interest_rate": loan.get("interest_rate"),
                "loan_tenure": loan.get("loan_term_months"),
                "loan_type": loan.get("loan_type"),
                "status": loan.get("status"),
                "created_at": loan.get("created_at"),
                "outstanding_amount": float(outstanding)
            })

        return jsonify({
            "status": "success",
            "customer": member,
            "loans": loan_list
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@admin_api_bp.route('/member-details-by-kgid', methods=['GET'])
def member_details_by_kgid():
    kgid = request.args.get('kgid')
    if not kgid:
        return jsonify({'status': 'error', 'message': 'kgid required'}), 400
    try:
        resp = supabase.table("members").select("customer_id,kgid").eq("kgid", kgid).limit(1).execute()
        if resp.data and len(resp.data) > 0:
            return jsonify({'status': 'success', 'member': resp.data[0]}), 200
        return jsonify({'status': 'error', 'message': 'KGID not found'}), 404
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@admin_api_bp.route('/recent-transactions', methods=['GET'])
def recent_transactions():
    # 6) Fixed Deposits (FDs)
    try:
        fd_resp = supabase.table('fixed_deposits') \
            .select('customer_id,amount,deposit_date,tenure,status,fdid,closed_at,payout_amount,withdrawal_id') \
            .gte('deposit_date', start_str).lt('deposit_date', end_str).execute()
        fds = fd_resp.data if hasattr(fd_resp, 'data') and fd_resp.data else []
        for fd in fds:
            try:
                amt = float(fd.get('amount') or 0)
            except Exception:
                amt = 0.0
            events.append({
                'type': 'FD Opened',
                'amount': round(amt, 2),
                'date': str(fd.get('deposit_date') or ''),
                'details': f"Customer: {fd.get('customer_id') or '-'}, Tenure: {fd.get('tenure') or '-'} months",
                'ref_id': fd.get('fdid')
            })
            # If closed, add FD Closed event
            if fd.get('closed_at'):
                payout = float(fd.get('payout_amount') or 0)
                events.append({
                    'type': 'FD Closed',
                    'amount': round(payout, 2),
                    'date': str(fd.get('closed_at') or ''),
                    'details': f"Customer: {fd.get('customer_id') or '-'}, FDID: {fd.get('fdid') or '-'}",
                    'ref_id': fd.get('withdrawal_id') or fd.get('fdid')
                })
    except Exception:
        pass
    """
    Aggregate recent transactions across multiple sources for a given date.
    Query params (optional):
      - year (defaults to current UTC year)
      - month (defaults to current UTC month)
      - day (defaults to current UTC day)
    If only year provided -> whole year; if year+month -> whole month; if all -> that specific day.

    Returns: { status, range: {start, end}, events: [
      { type, amount, date, details, ref_id }
    ] }
    """
    try:
        now = datetime.utcnow()
        year = int(request.args.get('year', now.year))
        month = request.args.get('month')
        day = request.args.get('day')

        if month is not None:
            month = int(month)
            if month < 1 or month > 12:
                return jsonify({'status': 'error', 'message': 'month must be 1-12'}), 400
        if day is not None:
            day = int(day)
            if day < 1 or day > 31:
                return jsonify({'status': 'error', 'message': 'day must be 1-31'}), 400

        # Determine start/end range [start, end)
        if day is not None and month is not None:
            try:
                start_dt = datetime(year, month, day)
            except ValueError:
                return jsonify({'status': 'error', 'message': 'Invalid day for the given month'}), 400
            end_dt = start_dt + timedelta(days=1)
        elif month is not None:
            start_dt = datetime(year, month, 1)
            end_dt = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
        else:
            start_dt = datetime(year, 1, 1)
            end_dt = datetime(year + 1, 1, 1)

        start_str = start_dt.strftime('%Y-%m-%d')
        end_str = end_dt.strftime('%Y-%m-%d')

        events = []

        # 1) Deposits & Withdrawals from transactions
        try:
            tx_resp = supabase.table('transactions') \
                .select('type,amount,date,customer_id,transaction_id') \
                .gte('date', start_str).lt('date', end_str).execute()
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
                events.append({
                    'type': label,
                    'amount': round(amt, 2),
                    'date': str(tx.get('date') or ''),
                    'details': f"Customer: {tx.get('customer_id') or '-'}",
                    'ref_id': tx.get('transaction_id')
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
                    events.append({
                        'type': 'Loan Approved',
                        'amount': round(amt, 2),
                        'date': str(ln.get('created_at') or ''),
                        'details': f"Customer: {ln.get('customer_id') or '-'}",
                        'ref_id': ln.get('loan_id')
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
                events.append({
                    'type': 'Loan Repayment',
                    'amount': round(amt, 2),
                    'date': str(r.get('repayment_date') or ''),
                    'details': f"Loan: {r.get('loan_id') or '-'}",
                    'ref_id': r.get('loan_id')
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
                events.append({
                    'type': 'Expense',
                    'amount': round(amt, 2),
                    'date': str(e.get('date') or ''),
                    'details': e.get('name') or 'Expense',
                    'ref_id': e.get('id')
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
                events.append({
                    'type': 'Staff Salary',
                    'amount': round(amt, 2),
                    'date': str(s.get('date') or ''),
                    'details': str(who),
                    'ref_id': s.get('transaction_id')
                })
        except Exception:
            pass

        # Sort events by date desc (string compare on ISO works with YYYY-MM-DD)
        try:
            events.sort(key=lambda x: str(x.get('date') or ''), reverse=True)
        except Exception:
            pass

        return jsonify({
            'status': 'success',
            'range': {'start': start_str, 'end': end_str},
            'events': events
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@admin_api_bp.route('/recent-transactions/excel', methods=['GET'])
def recent_transactions_excel():
    # 6) Fixed Deposits (FDs)
    try:
        fd_resp = supabase.table('fixed_deposits') \
            .select('customer_id,amount,deposit_date,tenure,status,fdid,closed_at,payout_amount,withdrawal_id') \
            .gte('deposit_date', start_str).lt('deposit_date', end_str).execute()
        fds = fd_resp.data if hasattr(fd_resp, 'data') and fd_resp.data else []
        for fd in fds:
            try:
                amt = float(fd.get('amount') or 0)
            except Exception:
                amt = 0.0
            excel_data.append({
                'Date': str(fd.get('deposit_date') or ''),
                'Type': 'FD Opened',
                'Amount': round(amt, 2),
                'Details': f"Customer: {fd.get('customer_id') or '-'}, Tenure: {fd.get('tenure') or '-'} months",
                'Reference ID': fd.get('fdid')
            })
            # If closed, add FD Closed event
            if fd.get('closed_at'):
                payout = float(fd.get('payout_amount') or 0)
                excel_data.append({
                    'Date': str(fd.get('closed_at') or ''),
                    'Type': 'FD Closed',
                    'Amount': round(payout, 2),
                    'Details': f"Customer: {fd.get('customer_id') or '-'}, FDID: {fd.get('fdid') or '-'}",
                    'Reference ID': fd.get('withdrawal_id') or fd.get('fdid')
                })
    except Exception:
        pass
    """
    Export recent transactions as Excel (.xlsx) for admin.
    Aggregates data from transactions, loans, loan_records, expenses, and staff_salaries tables.
    Query params: year, month, day (all optional)
    Returns: Excel file with all transaction types
    """
    try:
        now = datetime.utcnow()
        year = int(request.args.get('year', now.year))
        month = request.args.get('month')
        day = request.args.get('day')

        if month is not None:
            month = int(month)
            if month < 1 or month > 12:
                return jsonify({'status': 'error', 'message': 'month must be 1-12'}), 400
        if day is not None:
            day = int(day)
            if day < 1 or day > 31:
                return jsonify({'status': 'error', 'message': 'day must be 1-31'}), 400

        # Determine start/end range [start, end)
        if day is not None and month is not None:
            try:
                start_dt = datetime(year, month, day)
            except ValueError:
                return jsonify({'status': 'error', 'message': 'Invalid day for the given month'}), 400
            end_dt = start_dt + timedelta(days=1)
        elif month is not None:
            start_dt = datetime(year, month, 1)
            end_dt = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
        else:
            start_dt = datetime(year, 1, 1)
            end_dt = datetime(year + 1, 1, 1)

        start_str = start_dt.strftime('%Y-%m-%d')
        end_str = end_dt.strftime('%Y-%m-%d')

        excel_data = []

        # 1) Deposits & Withdrawals from transactions
        try:
            tx_resp = supabase.table('transactions') \
                .select('type,amount,date,customer_id,transaction_id') \
                .gte('date', start_str).lt('date', end_str).execute()
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
        response.headers["Content-Disposition"] = "attachment; filename=recent_transactions_complete.xlsx"
        response.headers["Content-Type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        return response
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Failed to generate Excel: {str(e)}'}), 500


