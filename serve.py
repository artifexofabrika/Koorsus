"""
serve.py — Production entry point for the Koorsus appliance.

Uses waitress instead of Flask's development server.
Launched by systemd; do not run interactively in production.
"""

from waitress import serve
import app as flask_app

if __name__ == "__main__":
    serve(
        flask_app.app,
        host="0.0.0.0",
        port=5000,
        threads=4,
        connection_limit=100,
        channel_timeout=120,
    )
