# app/routes/users.py
"""User route handlers."""
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
