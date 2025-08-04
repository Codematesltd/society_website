from . import notification_bp

@notification_bp.route("/inbox")
def inbox():
    return "<h1>Notification Inbox</h1>"
