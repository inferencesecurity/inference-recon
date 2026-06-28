# Security Review — demo-project

Scanned 11 files at 2026-05-23T15:00:00Z using claude-opus-4-7 (prompt v0.1).

## Scorecard

| Domain | Grade |
|---|---|
| Code | D |
| Dependencies | D |
| Secrets & Config | F |
| Architecture | F |
| **Overall** | **F** |

**Counts:** 2 critical, 2 high, 0 medium, 0 low, 0 info — high-confidence: 4, medium: 0, low: 0.

## Notes

- This envelope was captured against a pre-sanitization version of `demo-project/app/services/payments.py` that contained a real-shaped Stripe live key. The current `demo-project/` has a placeholder on the same line for public-repo safety. The finding at id `efa49c68` demonstrates what the model produces when a real-shaped credential is present; running the prompt against the current sanitized demo-project will not reproduce this exact finding (the placeholder body should not trigger `SECRET_hardcoded` at high confidence per the rubric's negative anchors).

## Critical findings (2)

### Stripe live API key hardcoded in payments module

| Field | Value |
|---|---|
| Severity | `critical` |
| Confidence | `high` |
| Category | `SECRET_hardcoded` |
| Domain | Secrets & Config |
| OWASP | A05 |
| Finding ID | `efa49c68` |

**Evidence** — `app/services/payments.py:7-7`

```
STRIPE_API_KEY = "sk_live_51HxYzABcdEfGhIjKlMnOpQrStUvWxYzAbCdEfGhIjKlMnOp"
```

**Exploitation path.** Anyone with read access to the source repository (current employees, former employees with retained access, any compromise of a developer machine, any leak of the repo) obtains a live Stripe key. The 'sk_live_' prefix indicates a production secret with permission to create charges, issue refunds, and read customer payment data. The in-code comment acknowledging a prior rotation confirms the key is in active production use.

**Remediation.** 1) Rotate the Stripe key immediately via the Stripe dashboard. 2) Move the key out of source — load from environment variable (os.environ['STRIPE_API_KEY']) or a secrets manager. 3) Audit git history; if the key was committed at any point, treat history as compromised and rotate regardless. 4) Add a pre-commit hook (gitleaks or similar) to prevent recurrence.

**References**
- CWE-798
- https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html

---

### Admin blueprint mounted with no authorization middleware

| Field | Value |
|---|---|
| Severity | `critical` |
| Confidence | `high` |
| Category | `ARCH_missing_authz` |
| Domain | Architecture |
| OWASP | A01 |
| Finding ID | `c77f6ce8` |

**Evidence** — `app/__init__.py:22-23`

```
    # Admin routes
    app.register_blueprint(admin_bp, url_prefix="/admin")
```

**Related locations**

- `app/__init__.py:17-19`
  ```
      from app.routes.api import api_bp
      login_required_for_blueprint(api_bp)
      app.register_blueprint(api_bp, url_prefix="/api")
  ```
- `app/routes/admin.py:14-21`
  ```
  @admin_bp.route("/users/<int:user_id>/promote", methods=["POST"])
  def promote_user(user_id):
      """Grant admin role to the specified user."""
      user = User.query.get_or_404(user_id)
      user.role = "admin"
      user.save()
      AuditLog.record(action="promote", target=user_id)
      return jsonify({"ok": True, "user_id": user_id})
  ```

**Exploitation path.** The /api blueprint has login_required_for_blueprint applied (app/__init__.py lines 17-19); the /admin blueprint does not. Every route under /admin is therefore reachable by any unauthenticated HTTP caller. GET /admin/users exposes the full user table (PII); POST /admin/users/<id>/promote lets an unauthenticated attacker grant themselves the admin role on any account they can identify, and the audit log entry will be written without an actor, making detection harder; GET /admin/audit-log exposes the audit trail itself. The asymmetry with the /api blueprint is strong evidence this is an oversight, not an intentional design.

**Remediation.** Apply the same blueprint-level auth that /api uses: insert login_required_for_blueprint(admin_bp) immediately before app.register_blueprint(admin_bp, ...) in create_app(). Better: require a role check, not just authentication, since this is an admin surface — e.g., login_required_for_blueprint(admin_bp, role="admin"). Additionally, add a per-handler @require_role("admin") decorator as defense-in-depth. Add an integration test that asserts every /admin/* route returns 401 or 403 without a valid admin session.

**References**
- CWE-862
- CWE-285
- https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html

## High findings (2)

### SQL injection via unescaped user_id in /users/<id> route

| Field | Value |
|---|---|
| Severity | `high` |
| Confidence | `high` |
| Category | `CODE_injection` |
| Domain | Code |
| OWASP | A03 |
| Finding ID | `4fab2d2f` |

**Evidence** — `app/routes/users.py:18-19`

```
    query = f"SELECT id, email, role FROM users WHERE id = {user_id}"
    cur.execute(query)
```

**Exploitation path.** Any HTTP caller can supply a crafted path segment (e.g., GET /users/1%20OR%201=1%20--) to bypass the intended row filter and dump the users table. Because the route converter is the default (string) and the value is f-string-interpolated into the SQL, no sanitization layer stands between the request and the query. With UNION SELECT, an attacker can exfiltrate adjacent tables that the DB user can read.

**Remediation.** Use a parameterized query: cur.execute("SELECT id, email, role FROM users WHERE id = ?", (user_id,)) (sqlite3 placeholder is '?'; psycopg2 uses '%s'). Change the route converter to <int:user_id> so non-integer input is rejected by Flask before reaching the handler.

**References**
- CWE-89
- https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html

---

### PyYAML 5.3.1 vulnerable to arbitrary code execution (CVE-2020-14343)

| Field | Value |
|---|---|
| Severity | `high` |
| Confidence | `high` |
| Category | `DEP_known_cve` |
| Domain | Dependencies |
| OWASP | A06 |
| Finding ID | `85934c06` |

**Evidence** — `requirements.txt:4-4`

```
PyYAML==5.3.1
```

**Related locations**

- `app/services/config_loader.py:6-7`
  ```
      with open(path) as f:
          return yaml.load(f, Loader=yaml.FullLoader)
  ```

**Exploitation path.** PyYAML versions before 5.4 allow arbitrary code execution when untrusted YAML is processed with yaml.load() under the default or FullLoader, via Python tag constructors. config_loader.py calls yaml.load(f, Loader=yaml.FullLoader) on a caller-supplied path. If any flow allows user-controlled YAML to reach load_config() — a config-upload endpoint, a tenant-supplied config file, a CI step that ingests artifact metadata — an attacker can execute arbitrary Python in the process. The use of FullLoader (rather than SafeLoader) confirms the project is exposed to the patched-but-still-present vulnerability that 5.4 closes.

**Remediation.** 1) Upgrade PyYAML to >=6.0. 2) Switch yaml.load(..., Loader=yaml.FullLoader) to yaml.safe_load(...) in app/services/config_loader.py — this is the correct API for untrusted input and removes the vulnerable code path regardless of library version. 3) Add a dependency policy that flags PyYAML versions <5.4 in CI.

**References**
- CVE-2020-14343
- https://nvd.nist.gov/vuln/detail/CVE-2020-14343
- https://github.com/yaml/pyyaml/issues/420

**CVSS** — v3.1 `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H` (score 9.8)
