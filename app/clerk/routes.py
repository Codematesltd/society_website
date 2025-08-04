from . import clerk_bp

@clerk_bp.route("/dashboard")
def dashboard():
    return "<h1>Clerk Dashboard</h1>"
