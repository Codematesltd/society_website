import os
from datetime import timedelta
from flask import Flask, redirect, url_for, session, request, abort, render_template  # Add session import
from app import create_app
from app.certificate import certificate_bp
from jinja2 import ChoiceLoader, FileSystemLoader

app = create_app()

# Set a secret key for sessions - add this line
app.secret_key = os.environ.get('SECRET_KEY', 'dev_secret_key_change_in_production')

# Use Flask built-in session (remove dependency on Flask-Session)
# configure session lifetime (1 hour)
app.permanent_session_lifetime = timedelta(seconds=3600)

# Tell Jinja about our custom templates directory
app.jinja_loader = ChoiceLoader([
    FileSystemLoader(os.path.join(os.path.dirname(__file__), 'templates')),
    app.jinja_loader
])

# Register certificate blueprint only if not already added
if 'certificate' not in app.blueprints:
    app.register_blueprint(certificate_bp)

# Register main routes blueprint (not registered in create_app)
try:
    from app.main import main_bp
    if 'main' not in app.blueprints:
        app.register_blueprint(main_bp)
    print("Main blueprint registered successfully")
except ImportError as e:
    print(f"Failed to import main blueprint: {e}")

# Register auth blueprint only if not already registered
try:
    from app.auth import auth_bp
    if 'auth' not in app.blueprints:
        app.register_blueprint(auth_bp)
        print("Auth blueprint registered successfully")
    else:
        print("Auth blueprint already registered (skipped)")
except ImportError as e:
    print(f"Failed to import auth blueprint: {e}")

# Register staff API blueprint (for /staff/api endpoints)
try:
    from app.staff.api import staff_api_bp, staff_bp
    if 'staff_api' not in app.blueprints:
        app.register_blueprint(staff_api_bp)
        print("Staff API blueprint registered successfully")
    else:
        print("Staff API blueprint already registered (skipped)")
    if 'staff' not in app.blueprints:
        app.register_blueprint(staff_bp)
        print("Staff blueprint registered successfully")
    else:
        print("Staff blueprint already registered (skipped)")
except ImportError as e:
    print(f"Failed to import staff blueprint: {e}")

# Register finance blueprint only if not already registered
try:
    from app.finance import finance_bp
    if 'finance' not in app.blueprints:
        app.register_blueprint(finance_bp)
        print("Finance blueprint registered successfully")
    else:
        print("Finance blueprint already registered (skipped)")
except ImportError as e:
    print(f"Failed to import finance blueprint: {e}")

# --- Proxy endpoints to support /finance/api/* paths if blueprint uses a different prefix ---
try:
    # import the view functions from finance API
    from app.finance.api import check_surety_get, fetch_account, apply_loan, fetch_customer_details
    from flask import request, session as flask_session

    @app.route('/finance/api/check-surety', methods=['GET'])
    def _proxy_check_surety():
        return check_surety_get()

    @app.route('/finance/api/fetch-account', methods=['GET'])
    def _proxy_fetch_account():
        return fetch_account()

    # NEW: Add the missing fetch_customer_details proxy
    @app.route('/finance/api/fetch_customer_details', methods=['GET'])
    def _proxy_fetch_customer_details():
        return fetch_customer_details()

    # NEW: proxy POST /finance/api/apply -> finance.api.apply_loan
    @app.route('/finance/api/apply', methods=['POST'])
    def _proxy_apply():
        """
        Proxy that allows providing staff identity via:
          - session['staff_email'] (normal)
          - X-Staff-Email header (fallback)
          - 'staff_email' field in JSON body (fallback)
        """
        # 1) header fallback
        header_email = request.headers.get('X-Staff-Email')
        if header_email:
            try:
                flask_session['staff_email'] = header_email
            except Exception:
                # session may not be available in some contexts; ignore if cannot set
                pass
        else:
            # 2) json body fallback
            try:
                body = request.get_json(silent=True) or {}
                body_email = body.get('staff_email')
                if body_email:
                    try:
                        flask_session['staff_email'] = body_email
                    except Exception:
                        pass
            except Exception:
                pass

        return apply_loan()

except Exception as _e:
    print(f"❌ [ERROR] Failed to register finance API proxies: {_e}")
    # if finance.api isn't available yet, skip proxy registration

# Register standalone api handlers in the project root (e.g. api/check_expenses.py)
try:
    from api.check_expenses import bp_expenses
    if 'check_expenses_api' not in app.blueprints:
        app.register_blueprint(bp_expenses)
        print("check_expenses blueprint registered successfully")
    else:
        print("check_expenses blueprint already registered (skipped)")
except ImportError as e:
    print(f"api.check_expenses not found or failed to import: {e}")

try:
    from app.finance.api import get_loan
    from flask import request, jsonify

    @app.route('/finance/<loan_id>', methods=['GET'])
    def _proxy_finance_loan_detail(loan_id):
        try:
            # Defensive: always return JSON, never propagate HTML errors
            resp = get_loan(loan_id)
            # If get_loan returns a tuple (jsonify, status), just return it
            if isinstance(resp, tuple):
                return resp
            # If resp is a Flask Response, check content type
            if hasattr(resp, 'content_type') and resp.content_type.startswith('application/json'):
                return resp
            # If resp is a dict, jsonify it
            if isinstance(resp, dict):
                return jsonify(resp)
            # If resp is a string, try to parse as JSON, else wrap as error
            try:
                import json
                return jsonify(json.loads(resp))
            except Exception:
                return jsonify({
                    "status": "error",
                    "message": "Loan API returned invalid response"
                }), 500
        except Exception as e:
            import traceback
            print("Loan fetch error:", traceback.format_exc())
            return jsonify({
                "status": "error",
                "message": f"Failed to fetch loan details: {str(e)}"
            }), 500
except Exception as e:
    print(f"Failed to register /finance/<loan_id> proxy: {e}")
    # Provide a fallback implementation if the import fails
    @app.route('/finance/<loan_id>', methods=['GET'])
    def _fallback_finance_loan_detail(loan_id):
        return jsonify({
            "status": "error",
            "message": "Finance API not available"
        }), 500

@app.route("/first_time_signin")
def first_time_signin_root():
    # Redirect legacy /first_time_signin to the auth blueprint page
    return redirect(url_for("auth.first_time_signin_page"))

# Add loan repayment route to serve the template
@app.route('/loan_repayment')
def loan_repayment():
    """Serve the loan repayment page"""
    return render_template('loan_repayment.html')

# Add alias endpoint so url_for('manager.manager_login') resolves.
# Redirects to the actual manager endpoint suggested by the BuildError.
try:
	# avoid overriding if already present
	if 'manager.manager_login' not in app.view_functions:
		@app.route('/manager/login', endpoint='manager.manager_login')
		def _manager_login_alias():
			# Redirect to the real manager view if available, otherwise 404.
			try:
				return redirect(url_for('manager.approve_loan_application'))
			except Exception:
				from flask import abort
				abort(404)
except Exception:
	# If app isn't fully initialized, skip creating the alias
	pass

# Ensure a root-level /logout works for frontend links by forwarding to the auth blueprint logout.
try:
    # avoid overriding if already present
    if 'root.logout' not in app.view_functions:
        @app.route('/logout', endpoint='root.logout')
        def _root_logout_redirect():
            try:
                return redirect(url_for('auth.logout'))
            except Exception:
                # fallback: redirect directly to login path
                return redirect('/login')
except Exception:
    pass

def is_sql_injection(value: str) -> bool:
    """
    Simple SQL injection detection for user input.
    Returns True if suspicious patterns are found.
    """
    if not isinstance(value, str):
        return False
    # Common SQLi patterns (case-insensitive)
    patterns = [
        r"(\%27)|(\')|(\-\-)|(\%23)|(#)",  # single quote, comment
        r"(\%22)|(\")",                   # double quote
        r"(\%3D)|(=)",                    # equal sign
        r"(\b(OR|AND)\b\s+\d+=\d+)",      # OR/AND 1=1
        r"(\bUNION\b|\bSELECT\b|\bINSERT\b|\bUPDATE\b|\bDELETE\b|\bDROP\b|\bALTER\b|\bCREATE\b)",  # SQL keywords
        r"(\bWHERE\b|\bFROM\b|\bTABLE\b|\bDATABASE\b)",
        r"(\bEXEC\b|\bEXECUTE\b|\bCAST\b|\bCONVERT\b)",
        r"(\bSLEEP\b|\bBENCHMARK\b|\bWAITFOR\b)",
    ]
    import re
    for pat in patterns:
        if re.search(pat, value, re.IGNORECASE):
            return True
    return False

from flask import request, abort
from functools import wraps
import time

# --- DDoS Protection: Simple Rate Limiting (per IP, per endpoint) ---
RATE_LIMITS = {}
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX = 30     # max requests per window per IP per endpoint

def rate_limit(limit=RATE_LIMIT_MAX, window=RATE_LIMIT_WINDOW):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            ip = request.remote_addr or "unknown"
            endpoint = request.endpoint or f.__name__
            now = int(time.time())
            key = f"{ip}:{endpoint}:{now // window}"
            count = RATE_LIMITS.get(key, 0)
            if count >= limit:
                abort(429, "Too many requests. Please try again later.")
            RATE_LIMITS[key] = count + 1
            return f(*args, **kwargs)
        return wrapped
    return decorator

# Apply rate limiting to sensitive endpoints (login, manager_login, etc.)
@app.before_request
def block_sql_injection_and_ddos():
    # SQL Injection protection (existing)
    if request.endpoint in ['auth.login', 'manager.manager_login']:
        for v in list(request.form.values()) + list(request.args.values()):
            if is_sql_injection(v):
                abort(400, "Potential SQL injection detected.")
        if request.is_json:
            for v in (request.get_json(silent=True) or {}).values():
                if isinstance(v, str) and is_sql_injection(v):
                    abort(400, "Potential SQL injection detected.")

    # DDoS protection (rate limit)
    sensitive_endpoints = ['auth.login', 'manager.manager_login']
    if request.endpoint in sensitive_endpoints:
        ip = request.remote_addr or "unknown"
        endpoint = request.endpoint
        now = int(time.time())
        key = f"{ip}:{endpoint}:{now // RATE_LIMIT_WINDOW}"
        count = RATE_LIMITS.get(key, 0)
        if count >= RATE_LIMIT_MAX:
            abort(429, "Too many requests. Please try again later.")
        RATE_LIMITS[key] = count + 1

# Ensure /finance/repay-loan POST is routed to the blueprint handler
# This must be present in your main app file to forward POST requests to the blueprint

@app.route('/finance/repay-loan', methods=['POST'])
def proxy_repay_loan():
    # Import inside function to avoid circular import issues
    from app.finance.api import repay_loan
    return repay_loan()

if __name__ == "__main__":
    app.run(debug=True)

