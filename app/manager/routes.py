from . import manager_bp

@manager_bp.route("/dashboard")
def dashboard():
    return "<h1>Manager Dashboard</h1>"
