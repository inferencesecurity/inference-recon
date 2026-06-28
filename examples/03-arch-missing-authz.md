# Example 03 — ARCH_missing_authz (Multi-file architectural gap)

**Demonstrates:** the schema's killer feature — `related_locations` array tying together an architectural decision and the concrete endpoints it impacts. Also exercises the `ARCH_*` exploitation_path requirement (mandatory regardless of severity per D13), critical severity, OWASP A01 cross-reference.

This is the kind of finding existing scanners typically miss: no single line is "wrong" in the SAST sense; the gap is in *how the pieces fit together*.

## Vulnerable code

`app/__init__.py`:

```python
# app/__init__.py
from flask import Flask
from app.routes.admin import admin_bp
from app.routes.public import public_bp
from app.auth import login_required_for_blueprint


def create_app():
    app = Flask(__name__)
    app.config.from_object("app.config.Production")

    # Public routes — no auth needed by design.
    app.register_blueprint(public_bp)

    # API routes get auth middleware applied at the blueprint level.
    from app.routes.api import api_bp
    login_required_for_blueprint(api_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    # Admin routes
    app.register_blueprint(admin_bp, url_prefix="/admin")

    return app
```

`app/routes/admin.py`:

```python
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
```

## Expected finding

```json
{
  "id": "affdfb1d",
  "category": "ARCH_missing_authz",
  "owasp_mapping": ["A01"],
  "severity": "critical",
  "confidence": "high",
  "title": "Admin blueprint mounted with no authorization middleware",
  "evidence": {
    "file": "app/__init__.py",
    "line_start": 22,
    "line_end": 23,
    "quote": "    # Admin routes\n    app.register_blueprint(admin_bp, url_prefix=\"/admin\")"
  },
  "related_locations": [
    {
      "file": "app/__init__.py",
      "line_start": 17,
      "line_end": 19,
      "quote": "    from app.routes.api import api_bp\n    login_required_for_blueprint(api_bp)\n    app.register_blueprint(api_bp, url_prefix=\"/api\")"
    },
    {
      "file": "app/routes/admin.py",
      "line_start": 8,
      "line_end": 10,
      "quote": "@admin_bp.route(\"/users\")\ndef list_users():\n    \"\"\"List every user account.\"\"\""
    },
    {
      "file": "app/routes/admin.py",
      "line_start": 14,
      "line_end": 21,
      "quote": "@admin_bp.route(\"/users/<int:user_id>/promote\", methods=[\"POST\"])\ndef promote_user(user_id):\n    \"\"\"Grant admin role to the specified user.\"\"\"\n    user = User.query.get_or_404(user_id)\n    user.role = \"admin\"\n    user.save()\n    AuditLog.record(action=\"promote\", target=user_id)\n    return jsonify({\"ok\": True, \"user_id\": user_id})"
    }
  ],
  "exploitation_path": "The /api blueprint has login_required_for_blueprint applied; the /admin blueprint does not. Every route under /admin is therefore reachable by any unauthenticated HTTP caller. Specifically: GET /admin/users exposes the full user table (PII); POST /admin/users/<id>/promote lets an unauthenticated attacker grant themselves the admin role on any account they can identify (and the audit log entry will be written without an actor, making detection harder); GET /admin/audit-log exposes the audit trail itself. None of the routes apply per-handler authorization either, so the missing middleware is the sole defense — and it is absent. The asymmetry with the /api blueprint is strong evidence this is an oversight, not an intentional design.",
  "remediation": "Apply the same blueprint-level auth that /api uses: insert login_required_for_blueprint(admin_bp) immediately before app.register_blueprint(admin_bp, ...) in create_app(). Better: require a role check, not just authentication, since this is an admin surface — e.g., login_required_for_blueprint(admin_bp, role=\"admin\"). Additionally, add a per-handler @require_role(\"admin\") decorator as defense-in-depth so that future refactoring of the blueprint registration doesn't silently un-protect the routes. Add an integration test that asserts every /admin/* route returns 401 or 403 without a valid admin session.",
  "references": [
    "CWE-862",
    "CWE-285",
    "https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html"
  ]
}
```

## What makes this a quality finding

The `evidence` is the architectural decision itself — the blueprint registration line where authz middleware is conspicuously absent. The `related_locations` array does the work that a single-location schema couldn't: it (a) shows the *correct* pattern just above for contrast (the /api blueprint's middleware application), and (b) names the specific endpoints that are now exposed, with enough quote context that the reader can see what each endpoint does. A reviewer reading this finding doesn't have to chase pointers across the repo — the entire chain of evidence is in one finding object.

The `exploitation_path` walks through each exposed endpoint and what an attacker gains from each. It also includes the meta-observation that the asymmetry with /api is itself evidence — this is not a design choice, it's an oversight. That kind of contextual reasoning is exactly where an LLM beats a SAST scanner.

The `remediation` provides the minimal fix (one-line insertion mirroring the /api pattern), the more correct fix (role check, not just authentication, because it's an admin surface), and a defense-in-depth recommendation plus a regression test. Three layers of guidance for one finding.

`severity` is `critical` because the impact includes privilege escalation by an unauthenticated attacker (the `/promote` endpoint). If the only exposed endpoints had been read-only, `high` would be more appropriate.

## What is NOT a finding in this code

The `public_bp` blueprint being registered without auth is NOT a finding — the comment explicitly states it's by design, and the asymmetric handling of /api (with auth) versus /public (without) suggests an intentional auth model. Don't flag every unauthenticated endpoint; only flag ones where the *intent* appears to have been protection that's missing.

The use of `query.all()` in `list_users` without pagination is a *performance* concern, not a security one (well — denial of service is a security concern, but it's a separate finding and at a much lower severity). Don't conflate the authz issue with the pagination issue.
