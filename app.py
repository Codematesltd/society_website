import os
from flask import Flask, redirect, url_for, session  # Add session import
from app import create_app
from app.certificate import certificate_bp
from jinja2 import ChoiceLoader, FileSystemLoader
from flask_session import Session

app = create_app()

# Set a secret key for sessions - add this line
app.secret_key = os.environ.get('SECRET_KEY', 'dev_secret_key_change_in_production')

# Configure session type (filesystem is simple for dev; use redis for prod)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # Session lifetime in seconds (1 hour)
Session(app)

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
    from app.finance.api import check_surety_get, fetch_account, apply_loan
    from flask import request, session as flask_session

    @app.route('/finance/api/check-surety', methods=['GET'])
    def _proxy_check_surety():
        return check_surety_get()

    @app.route('/finance/api/fetch-account', methods=['GET'])
    def _proxy_fetch_account():
        return fetch_account()

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
    # if finance.api isn't available yet, skip proxy registration
    pass

@app.route("/first_time_signin")
def first_time_signin_root():
    # Redirect legacy /first_time_signin to the auth blueprint page
    return redirect(url_for("auth.first_time_signin_page"))

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

if __name__ == "__main__":
    app.run(debug=True)
