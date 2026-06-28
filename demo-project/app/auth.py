# app/auth.py
"""Auth helpers for blueprint-level access control."""
from functools import wraps
from flask import request, abort


def login_required_for_blueprint(bp):
    """Apply a before_request guard that requires an authenticated session."""
    @bp.before_request
    def _check():
        if not request.cookies.get("session"):
            abort(401)
