"""
arkiv/app.py - Flask application factory.

Route families live in their own modules; this file only wires them
together. Endpoint names are unchanged, so url_for() and the login guard
behave exactly as before.
"""
from datetime import timedelta

from flask import Flask

import config
import auth
import ask_routes
import ingest_routes
import admin_routes
import users_routes

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
app.permanent_session_lifetime = timedelta(minutes=config.SESSION_TIMEOUT_MIN)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")

auth.register(app)
ask_routes.register(app)
ingest_routes.register(app)
admin_routes.register(app)
users_routes.register(app)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=False)
