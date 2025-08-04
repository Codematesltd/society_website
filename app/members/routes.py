from . import members_bp

@members_bp.route("/dashboard")
def dashboard():
    return "<h1>Members Dashboard</h1>"
