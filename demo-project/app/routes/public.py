# app/routes/public.py
"""Public routes — intentionally unauthenticated."""
from flask import Blueprint, jsonify

public_bp = Blueprint("public", __name__)


@public_bp.route("/health")
def health():
    return jsonify({"status": "ok"})


@public_bp.route("/")
def index():
    return jsonify({"app": "demo-project"})
