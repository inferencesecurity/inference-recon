# app/models.py
"""ORM models (stubs)."""


class User:
    id = None
    email = None
    role = None

    @classmethod
    def current(cls):
        return cls()

    def to_dict(self):
        return {"id": self.id, "email": self.email, "role": self.role}

    def save(self):
        pass


class AuditLog:
    @classmethod
    def record(cls, **kwargs):
        pass

    def to_dict(self):
        return {}
