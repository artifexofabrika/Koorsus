"""Authentication: username and PIN, with a shared-PIN fallback for first run.

If the users table is empty the appliance still accepts config.ARKIV_PIN with
any name, so a half-finished migration cannot lock anyone out. The moment a
named account exists, the fallback stops applying.
"""
import hmac
import time

from flask import (request, session, redirect, url_for, jsonify,
                   render_template_string, current_app)

import config
import users
from templates_html import LOGIN_PAGE

_FAILED = {}
_LOCK_MIN = 15
_MAX_FAILS = 5


def client_ip():
    """The client address. X-Forwarded-For is deliberately ignored: with no
    trusted proxy in front of Gunicorn, trusting it lets a caller rotate the
    header and never trip the lockout."""
    return request.remote_addr or "unknown"


def current_user():
    if not session.get("authenticated"):
        return None
    return {"id": session.get("user_id"), "name": session.get("user_name"),
            "role": session.get("role", "member")}


def is_locked(key):
    entry = _FAILED.get(key)
    if not entry:
        return False
    count, first_ts = entry
    if count < _MAX_FAILS:
        return False
    if time.time() - first_ts > _LOCK_MIN * 60:
        _FAILED.pop(key, None)
        return False
    return True


def record_fail(key):
    entry = _FAILED.get(key)
    if not entry or time.time() - entry[1] > _LOCK_MIN * 60:
        _FAILED[key] = [1, time.time()]
    else:
        entry[0] += 1


def clear_fails(key):
    _FAILED.pop(key, None)


def register(app):
    @app.route("/login", methods=["GET", "POST"])
    def login():
        nxt = request.args.get("next") or "/"
        error = None
        if request.method == "POST":
            username = (request.form.get("username") or "").strip()
            key = username.lower() + "|" + client_ip()
            if is_locked(key):
                error = "Too many failed attempts. Try again in a few minutes."
            else:
                entered = (request.form.get("pin") or "").strip()
                account = None
                try:
                    if users.count_users() == 0:
                        if hmac.compare_digest(entered, str(config.ARKIV_PIN)):
                            account = {"id": None, "name": username or "office",
                                       "role": "admin"}
                    else:
                        account = users.verify(username, entered)
                except Exception:
                    current_app.logger.exception("login lookup failed")
                    account = None
                if account:
                    session.permanent = True
                    session["authenticated"] = True
                    session["authed_at"] = int(time.time())
                    session["user_id"] = account["id"]
                    session["user_name"] = account["name"]
                    session["role"] = account.get("role", "member")
                    clear_fails(key)
                    target = request.form.get("next") or "/"
                    if not target.startswith("/"):
                        target = "/"
                    return redirect(target)
                else:
                    record_fail(key)
                    error = "Incorrect name or PIN."
        return render_template_string(LOGIN_PAGE, error=error, next=nxt)

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.before_request
    def require_login():
        if request.endpoint in ("login", "favicon", "static"):
            return None
        if session.get("authenticated"):
            return None
        if request.method == "GET" and request.path in ("/", "/ingest", "/admin", "/users"):
            return redirect(url_for("login", next=request.path))
        return jsonify({"error": "Not authenticated", "login": "/login"}), 401
