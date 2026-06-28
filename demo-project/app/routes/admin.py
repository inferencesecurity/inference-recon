# app/routes/admin.py
from flask import Blueprint, jsonify, request
from app.models import User, AuditLog

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/users")
def list_users():
    """List every user account."""
    return jsonify([u.to_dict() for u in User.query.all()])


@admin_bp.route("/users/<int:user_id>/promote", methods=["POST"])
def promote_user(user_id):
    """Grant admin role to the specified user."""
    user = User.query.get_or_404(user_id)
    user.role = "admin"
    user.save()
    AuditLog.record(action="promote", target=user_id)
    return jsonify({"ok": True, "user_id": user_id})


@admin_bp.route("/audit-log")
def view_audit_log():
    return jsonify([entry.to_dict() for entry in AuditLog.query.all()])
