from flask import render_template, jsonify, request, redirect, url_for
from . import admin_bp
from app.auth.routes import supabase
from datetime import datetime

@admin_bp.route('/pending-loans')
def pending_loan_approvals():
    """View for pending loan applications"""
    # Fetch loans with pending_approval status
    loans = supabase.table("loans").select("*").eq("status", "pending_approval").execute()
    
    return render_template('admin/loan_approvals.html', 
                          loans=loans.data if loans.data else [],
                          status="pending")

@admin_bp.route('/approved-loans')
def approved_loans():
    """View for approved loan applications"""
    # Fetch loans with approved status
    loans = supabase.table("loans").select("*").eq("status", "approved").execute()
    
    return render_template('admin/loan_approvals.html', 
                          loans=loans.data if loans.data else [],
                          status="approved")

@admin_bp.route('/rejected-loans')
def rejected_loans():
    """View for rejected loan applications"""
    # Fetch loans with rejected status
    loans = supabase.table("loans").select("*").eq("status", "rejected").execute()
    
    return render_template('admin/loan_approvals.html', 
                          loans=loans.data if loans.data else [],
                          status="rejected")

@admin_bp.route('/loan-details/<loan_id>')
def loan_details(loan_id):
    """View detailed information about a loan"""
    # Fetch loan details
    loan = supabase.table("loans").select("*").eq("id", loan_id).execute()
    if not loan.data:
        return jsonify({"status": "error", "message": "Loan not found"}), 404
    
    loan_data = loan.data[0]
    
    # Fetch customer details
    customer = None
    if loan_data.get("customer_id"):
        customer_data = supabase.table("members").select("*").eq("customer_id", loan_data["customer_id"]).execute()
        if customer_data.data:
            customer = customer_data.data[0]
    
    # Fetch sureties
    sureties = []
    sureties_data = supabase.table("sureties").select("*").eq("loan_id", loan_id).execute()
    if sureties_data.data:
        sureties = sureties_data.data
    
    return render_template('admin/loan_details.html', 
                          loan=loan_data,
                          customer=customer,
                          sureties=sureties)

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
