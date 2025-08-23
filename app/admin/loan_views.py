from flask import render_template, jsonify, request, redirect, url_for
from . import admin_bp
from app.auth.routes import supabase
from datetime import datetime, date
import math  # NEW
try:
    from httpx import RemoteProtocolError
except Exception:
    RemoteProtocolError = Exception  # fallback if import not available

def sb_exec(qb, attempts=3):
    """
    Execute a Supabase query builder with simple retries to handle transient
    'RemoteProtocolError: Server disconnected' issues.
    """
    last_err = None
    for i in range(attempts):
        try:
            return qb.execute()
        except RemoteProtocolError as e:
            last_err = e
            if i < attempts - 1:
                continue
            raise
        except Exception as e:
            # Pass through non protocol errors immediately
            raise
    if last_err:
        raise last_err

@admin_bp.route('/pending-loans')
def pending_loan_approvals():
    """View for pending loan applications"""
    # Fetch loans with pending_approval status
    loans_resp = sb_exec(supabase.table("loans").select("*").eq("status", "pending_approval"))
    loans = loans_resp.data if loans_resp.data else []
    
    return render_template('admin/loan_approvals.html', 
                          loans=loans,
                          status="pending")

@admin_bp.route('/approved-loans')
def approved_loans():
    """View for approved loan applications"""
    # Fetch loans with approved status
    loans_resp = sb_exec(supabase.table("loans").select("*").eq("status", "approved"))
    loans = loans_resp.data if loans_resp.data else []
    
    return render_template('admin/loan_approvals.html', 
                          loans=loans,
                          status="approved")

@admin_bp.route('/rejected-loans')
def rejected_loans():
    """View for rejected loan applications"""
    # Fetch loans with rejected status
    loans_resp = sb_exec(supabase.table("loans").select("*").eq("status", "rejected"))
    loans = loans_resp.data if loans_resp.data else []
    
    return render_template('admin/loan_approvals.html', 
                          loans=loans,
                          status="rejected")

@admin_bp.route('/loan-details/<loan_id>')
def loan_details(loan_id):
    """View detailed information about a loan"""
    # Fetch loan details
    loan_resp = sb_exec(supabase.table("loans").select("*").eq("id", loan_id))
    if not loan_resp.data:
        return jsonify({"status": "error", "message": "Loan not found"}), 404
    loan_data = loan_resp.data[0]

    # Fetch customer details
    customer = None
    if loan_data.get("customer_id"):
        customer_resp = sb_exec(supabase.table("members").select("*").eq("customer_id", loan_data["customer_id"]))
        if customer_resp.data:
            customer = customer_resp.data[0]
        else:
            customer = None

    # Fetch sureties
    sureties = []
    sureties_resp = sb_exec(supabase.table("sureties").select("*").eq("loan_id", loan_id))
    if sureties_resp.data:
        sureties = sureties_resp.data

    # --- FIX: Fetch repayment records for both textual loan_id and UUID ---
    loan_id_text = loan_data.get("loan_id")
    records = []
    if loan_id_text:
        rec_resp1 = sb_exec(supabase.table("loan_records").select("*").eq("loan_id", loan_id_text))
        rec_resp2 = sb_exec(supabase.table("loan_records").select("*").eq("loan_id", loan_id))
        # Merge and deduplicate by id
        seen = set()
        all_records = []
        for r in (rec_resp1.data or []) + (rec_resp2.data or []):
            if r["id"] not in seen:
                all_records.append(r)
                seen.add(r["id"])
        # Sort by repayment_date (oldest first, nulls last)
        records = sorted(all_records, key=lambda r: (r["repayment_date"] or "9999-12-31"))
    # ...existing code...

    # NEW: Compute metrics
    principal = float(loan_data.get("loan_amount", 0) or 0)
    annual_rate = float(loan_data.get("interest_rate", 0) or 0)
    term_months = int(loan_data.get("loan_term_months", 0) or 0)
    monthly_rate = annual_rate / 1200 if annual_rate else 0
    if monthly_rate and term_months:
        emi = principal * monthly_rate * (1 + monthly_rate) ** term_months / ((1 + monthly_rate) ** term_months - 1)
    else:
        emi = principal / term_months if term_months else 0
    emi = round(emi, 2)

    total_repaid = 0
    last_outstanding = principal
    for r in records:
        amt = float(r.get("repayment_amount") or 0)
        total_repaid += amt
        if r.get("outstanding_balance") is not None:
            last_outstanding = float(r.get("outstanding_balance"))
        else:
            last_outstanding = max(principal - total_repaid, 0)

    outstanding = max(principal - total_repaid, 0) if not records or not records[-1].get("outstanding_balance") else last_outstanding
    # Total scheduled payment & interest (standard EMI plan)
    total_payment_sched = round(emi * term_months, 2)
    total_interest_sched = round(total_payment_sched - principal, 2)

    # Elapsed months
    created_at = loan_data.get("created_at")
    elapsed_months = 0
    if created_at:
        try:
            dt_created = datetime.fromisoformat(str(created_at).replace('Z', '+00:00'))
            today = datetime.utcnow()
            elapsed_months = (today.year - dt_created.year) * 12 + (today.month - dt_created.month)
            elapsed_months = max(0, min(elapsed_months, term_months))
        except Exception:
            pass

    # Approx interest accrued (linear over term if EMI)
    interest_accrued_est = round(total_interest_sched * (elapsed_months / term_months), 2) if term_months else 0

    # Next due date
    next_due_date = None
    if created_at and term_months:
        try:
            base = datetime.fromisoformat(str(created_at).replace('Z', '+00:00'))
            next_index = min(elapsed_months + 1, term_months)
            year = base.year + (base.month - 1 + next_index) // 12
            month = (base.month - 1 + next_index) % 12 + 1
            day = min(base.day, 28)  # safe day
            next_due_date = date(year, month, day).isoformat()
        except Exception:
            pass

    metrics = {
        "principal": principal,
        "emi": emi,
        "annual_rate": annual_rate,
        "monthly_rate_percent": round(monthly_rate * 100, 4),
        "term_months": term_months,
        "total_payment_scheduled": total_payment_sched,
        "total_interest_scheduled": total_interest_sched,
        "total_repaid": round(total_repaid, 2),
        "outstanding": round(outstanding, 2),
        "elapsed_months": elapsed_months,
        "interest_accrued_est": interest_accrued_est,
        "next_due_date": next_due_date
    }

    return render_template('admin/loan_details.html',
                           loan=loan_data,
                           customer=customer,
                           sureties=sureties,
                           records=records,          # NEW
                           metrics=metrics)          # NEW

@admin_bp.route('/approve-loan/<loan_id>', methods=['POST'])
def admin_approve_loan(loan_id):
    """Admin endpoint to approve a loan"""
    try:
        # First, get the loan details to access amount and customer_id
        loan_details = supabase.table("loans").select("*").eq("id", loan_id).execute()
        if not loan_details.data:
            print(f"Error: Loan {loan_id} not found")
            return redirect(url_for('admin.pending_loan_approvals'))
            
        loan = loan_details.data[0]
        customer_id = loan.get("customer_id")
        loan_amount = loan.get("loan_amount")
        
        # Call the finance API to approve the loan
        from app.finance.api import approve_loan
        result = approve_loan(loan_id)
        
        # After loan is approved, deposit the amount to customer's account
        if result and customer_id and loan_amount:
            # 1. Update customer balance
            customer_result = supabase.table("members").select("balance").eq("customer_id", customer_id).execute()
            if customer_result.data:
                current_balance = customer_result.data[0].get("balance", 0)
                new_balance = current_balance + float(loan_amount)
                
                # Update member balance
                supabase.table("members").update({"balance": new_balance}).eq("customer_id", customer_id).execute()
                
                # 2. Create transaction record
                transaction_data = {
                    "customer_id": customer_id,
                    "amount": loan_amount,
                    "type": "deposit",
                    "description": f"Loan disbursement (Loan ID: {loan.get('loan_id')})",
                    "transaction_date": datetime.now().isoformat(),
                    "status": "completed"
                }
                
                # Create transaction record
                transaction_result = supabase.table("transactions").insert(transaction_data).execute()
                
                if transaction_result.data:
                    print(f"Successfully deposited loan amount of {loan_amount} to customer {customer_id}")
                else:
                    print(f"Warning: Failed to create transaction record for loan deposit")
            else:
                print(f"Warning: Customer {customer_id} not found, could not update balance")
    except Exception as e:
        print(f"Error approving loan: {e}")
    
    # Redirect to the pending loans page
    return redirect(url_for('admin.pending_loan_approvals'))

@admin_bp.route('/reject-loan/<loan_id>', methods=['POST'])
def admin_reject_loan(loan_id):
    """Admin endpoint to reject a loan"""
    reason = request.form.get('reason', 'Application rejected by administrator')
    
    try:
        # Instead of modifying request.json, call the finance API in a different way
        from app.finance.api import reject_loan
        
        # Create a proper JSON response for the reject_loan function
        # Import needed modules
        import json
        from flask import Response
        
        # Option 1: Directly update the loan in the database
        result = supabase.table("loans").update({
            "status": "rejected", 
            "rejection_reason": reason
        }).eq("id", loan_id).execute()
        
        # Option 2: Or call a modified version of reject_loan that takes reason directly
        # result = reject_loan_with_reason(loan_id, reason)
        
        if not result.data:
            print(f"Error: Loan {loan_id} not found or update failed")
    except Exception as e:
        print(f"Error rejecting loan: {e}")
    
    # Redirect to the pending loans page
    return redirect(url_for('admin.pending_loan_approvals'))

# Helper function to reject a loan without relying on request.json
def reject_loan_with_reason(loan_id, reason):
    """Reject a loan application with the specified reason"""
    resp = supabase.table("loans").update({
        "status": "rejected", 
        "rejection_reason": reason
    }).eq("id", loan_id).execute()
    
    if not resp.data:
        return {"status": "error", "message": "Loan not found or update failed"}, 404
        
    # Mark sureties as inactive for this loan
    supabase.table("sureties").update({"active": False}).eq("loan_id", loan_id).execute()
    
    # Send email notification if needed
    try:
        from app.finance.api import get_member_by_customer_id, send_loan_status_email
        member = get_member_by_customer_id(resp.data[0]["customer_id"])
        if member and member.get("name"):
            member_email_resp = supabase.table("members").select("email").eq("customer_id", resp.data[0]["customer_id"]).execute()
            if member_email_resp.data and member_email_resp.data[0].get("email"):
                send_loan_status_email(member_email_resp.data[0]["email"], member["name"], loan_id, "rejected")
    except Exception as e:
        print(f"Error sending notification: {e}")
        
    return {"status": "success"}, 200
