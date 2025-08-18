import os
from flask import Flask, redirect, url_for  # added redirect,url_for
from app import create_app
from app.certificate import certificate_bp
from jinja2 import ChoiceLoader, FileSystemLoader

app = create_app()

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

# Register staff blueprint if not already registered
try:
    from app.staff.api import staff_bp
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

@app.route("/first_time_signin")
def first_time_signin_root():
    # Redirect legacy /first_time_signin to the auth blueprint page
    return redirect(url_for("auth.first_time_signin_page"))

if __name__ == "__main__":
    app.run(debug=True)
