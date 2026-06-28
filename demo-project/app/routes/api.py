# app/routes/api.py
"""Authenticated API routes (auth applied at blueprint registration in __init__.py)."""
from flask import Blueprint, jsonify
from app.models import User

api_bp = Blueprint("api", __name__)


@api_bp.route("/me")
def me():
    return jsonify(User.current().to_dict())
