from . import admin_bp

@admin_bp.route("/dashboard")
def dashboard():
    return "<h1>Admin Dashboard</h1>"
