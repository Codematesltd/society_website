from flask import Blueprint, render_template, request, abort, make_response,jsonify
from supabase import create_client
import os
import inflect
import pdfkit
from datetime import datetime

loan_cert_bp = Blueprint('loan_cert', __name__)

# Helper for amount in words
p = inflect.engine()

def amount_to_words(amount):
    try:
        n = int(float(amount))
        words = p.number_to_words(n, andword='').replace(',', '')
        return words.title() + " Rupees Only"
    except Exception:
        return str(amount)

@loan_cert_bp.route('/loan/certificate/<loan_id>')
def loan_certificate(loan_id):
    action = request.args.get('action', 'view')
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Fetch loan
    loan_resp = supabase.table("loans").select("*").eq("loan_id", loan_id).execute()
    if not loan_resp.data:
        return jsonify({"status": "error", "message": "Loan not found"}), 404
    loan = loan_resp.data[0]

    # Fetch customer
    member_resp = supabase.table("members").select("name,photo_url").eq("customer_id", loan["customer_id"]).execute()
    member = member_resp.data[0] if member_resp.data else {}

    # Fetch staff
    staff_resp = supabase.table("staff").select("name,photo_url,signature_url").eq("email", loan["staff_email"]).execute()
    staff = staff_resp.data[0] if staff_resp.data else {}

    # Society info
    society_name = os.environ.get("SOCIETY_NAME", "Kushtagi Taluk High School Employees Cooperative Society Ltd., Kushtagi-583277")
    taluk_name = os.environ.get("TALUK_NAME", "Kushtagi")
    district_name = os.environ.get("DISTRICT_NAME", "koppala")

    # Render HTML
    html = render_template(
        "certificate.html",
        loan=loan,
        member=member,
        staff=staff,
        society_name=society_name,
        taluk_name=taluk_name,
        district_name=district_name,
        amount_words=amount_to_words(loan["loan_amount"])
    )

    if action == "download":
        pdf = pdfkit.from_string(html, False, options={'enable-local-file-access': None})
        response = make_response(pdf)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename={loan_id}.pdf'
        return response
    elif action == "print":
        # Add JS for print
        html += "<script>window.onload = function(){window.print();}</script>"
        return html
    else:
        return html

def register_certificate_routes(blueprint):
    """Register certificate routes on the provided blueprint"""
    
    @blueprint.route('/certificate/<certificate_id>', methods=['GET'])
    def view_loan_certificate(certificate_id):
        """Display the loan certificate"""
        action = request.args.get('action', 'view')
        
        try:
            # Query loan details by certificate_id
            result = supabase.table("loans").select("*").eq("certificate_id", certificate_id).execute()
            
            if not result.data or len(result.data) == 0:
                return abort(404, description="Certificate not found")
                
            loan = result.data[0]
            
            # Get customer details
            customer_result = supabase.table("members").select("*").eq("customer_id", loan["customer_id"]).execute()
            customer = customer_result.data[0] if customer_result.data else {}
            
            # Get staff details if available
            staff = {}
            if loan.get("staff_email"):
                staff_result = supabase.table("staff").select("*").eq("email", loan["staff_email"]).execute()
                staff = staff_result.data[0] if staff_result.data else {}
            
            # Format date for certificate
            issue_date = datetime.now().strftime("%d-%m-%Y")
            if loan.get("approved_at"):
                try:
                    approved_date = datetime.fromisoformat(loan["approved_at"]).strftime("%d-%m-%Y")
                    issue_date = approved_date
                except:
                    pass
                    
            certificate_data = {
                "loan_id": loan["loan_id"],
                "customer_name": customer.get("name", ""),
                "customer_id": loan["customer_id"],
                "loan_amount": loan["loan_amount"],
                "interest_rate": loan["interest_rate"],
                "loan_term_months": loan["loan_term_months"],
                "status": loan["status"],
                "issue_date": issue_date,
                "loan_type": loan["loan_type"],
                "staff_name": staff.get("name", ""),
            }
            
            if action == 'view':
                # Render HTML certificate
                return render_template('loan_certificate.html', loan=certificate_data)
            else:
                # Return JSON data
                return jsonify(certificate_data)
                
        except Exception as e:
            print(f"Error retrieving certificate: {e}")
            return abort(500, description="Error generating certificate")
