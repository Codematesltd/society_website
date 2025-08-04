from flask_login import UserMixin

class AdminUser(UserMixin):
    def __init__(self, id, email):
        self.id = id
        self.email = email
