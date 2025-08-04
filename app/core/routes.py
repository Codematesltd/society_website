from . import core_bp

@core_bp.route("/")
def home():
    return "<h1>Society Home Page</h1>"
