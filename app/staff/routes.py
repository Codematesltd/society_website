from . import staff_bp

@staff_bp.route("/dashboard")
def dashboard():
    return "<h1>Staff Dashboard</h1>"
