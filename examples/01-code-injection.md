# Example 01 — CODE_injection (SQL injection)

**Demonstrates:** classic code-level vulnerability, single-location evidence (no `related_locations` needed), high severity triggering `exploitation_path` requirement, OWASP A03 cross-reference.

## Vulnerable code

`app/routes/users.py`:

```python
# app/routes/users.py
from flask import Flask, request, jsonify
from app.db import get_connection

app = Flask(__name__)


@app.route("/users/<user_id>")
def get_user(user_id):
    """Return the user record matching the URL path segment."""
    conn = get_connection()
    cur = conn.cursor()

    # NOTE: user_id is interpolated directly into the SQL string.
    # The Flask route converter does not sanitize for SQL contexts.
    query = f"SELECT id, email, role FROM users WHERE id = {user_id}"
    cur.execute(query)

    row = cur.fetchone()
    if row is None:
        return jsonify({"error": "not found"}), 404
    return jsonify({"id": row[0], "email": row[1], "role": row[2]})
```

## Expected finding

```json
{
  "id": "fba03efa",
  "category": "CODE_injection",
  "owasp_mapping": ["A03"],
  "severity": "high",
  "confidence": "high",
  "title": "SQL injection via unescaped user_id in /users/<id> route",
  "evidence": {
    "file": "app/routes/users.py",
    "line_start": 18,
    "line_end": 19,
    "quote": "query = f\"SELECT id, email, role FROM users WHERE id = {user_id}\"\n    cur.execute(query)"
  },
  "exploitation_path": "Any HTTP caller can supply a crafted path segment (e.g., GET /users/1%20OR%201=1%20--) to bypass the intended row filter and dump the users table. Because the route converter is the default (string) and the value is f-string-interpolated into the SQL, no sanitization layer stands between the request and the query. With UNION SELECT, the attacker can exfiltrate adjacent tables that the DB user can read.",
  "remediation": "Use a parameterized query. With sqlite3/psycopg2/etc.: cur.execute(\"SELECT id, email, role FROM users WHERE id = %s\", (user_id,)). With SQLAlchemy: User.query.get(user_id). Additionally, change the route converter to <int:user_id> so non-integer input is rejected by Flask before reaching the handler.",
  "references": [
    "CWE-89",
    "https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html"
  ]
}
```

## What makes this a quality finding

The title names the specific vector (`user_id`) and the specific location (`/users/<id>` route) — a security reviewer skimming the report can grep for the route name and find the finding. The `evidence.quote` is verbatim and includes both the query construction and the execution call, so the reader can see the full vulnerable expression. The `exploitation_path` describes a concrete attack (`?user_id=1 OR 1=1 --`), names the attacker (any HTTP caller, no auth required), and mentions the lateral impact (UNION SELECT exfiltrating adjacent tables). The `remediation` names the exact API call to switch to and adds the defense-in-depth recommendation (route converter) — not just "use parameterized queries."

## What is NOT a finding in this code

The `if row is None: return jsonify(...), 404` branch is the correct pattern — it does not leak whether the ID format is valid versus whether the record exists, *given* the SQL injection is fixed. A noisy scanner might flag "information disclosure via 404 vs. 500." Don't. The 404 is appropriate. (After the injection is fixed, this branch is fine.)
