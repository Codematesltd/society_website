# Placeholder models for development
class User:
    def __init__(self, id, name, role="user"):
        self.id = id
        self.name = name
        self.role = role

class Loan:
    def __init__(self, id, amount, user_id, status="pending"):
        self.id = id
        self.amount = amount
        self.user_id = user_id
        self.status = status

class Transaction:
    def __init__(self, id, amount, type, user_id):
        self.id = id
        self.amount = amount
        self.type = type
        self.user_id = user_id
