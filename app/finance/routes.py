from . import finance_bp

@finance_bp.route("/dashboard")
def dashboard():
    return "<h1>Finance Dashboard</h1>"
