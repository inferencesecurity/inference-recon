# app/db.py
"""Database connection helper (stub)."""
import sqlite3


def get_connection():
    return sqlite3.connect("demo.db")
