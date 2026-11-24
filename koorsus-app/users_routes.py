"""User administration, self-service PIN change, and query log export."""
from flask import (request, redirect, url_for, render_template_string,
                   Response)

import users
from auth import current_user
from templates_users import USERS_PAGE


def _is_admin():
    u = current_user()
    return bool(u and u.get("role") == "admin")


def register(app):
    @app.route("/users", methods=["GET", "POST"])
    def users_page():
        u = current_user()
        if not u:
            return redirect(url_for("login", next="/users"))
        msg, err = None, False
        if request.method == "POST":
            action = request.form.get("action") or ""
            if action == "selfpin":
                current = (request.form.get("current_pin") or "").strip()
                new1 = (request.form.get("new_pin") or "").strip()
                new2 = (request.form.get("new_pin2") or "").strip()
                if not users.verify(u["name"], current):
                    msg, err = "Current PIN is incorrect.", True
                elif new1 != new2:
                    msg, err = "The two new PINs do not match.", True
                else:
                    try:
                        users.set_pin(u["id"], new1)
                        msg = "Your PIN has been updated."
                    except Exception as e:
                        msg, err = str(e), True
            elif not _is_admin():
                msg, err = "Only an administrator can do that.", True
            elif action == "add":
                name = (request.form.get("name") or "").strip()
                pin = (request.form.get("pin") or "").strip()
                role = (request.form.get("role") or "member").strip()
                if not name:
                    msg, err = "A name is required.", True
                else:
                    try:
                        users.create_user(name, pin, role)
                        msg = "Created " + name + "."
                    except Exception as e:
                        msg, err = str(e), True
            elif action == "active":
                users.set_active(int(request.form.get("user_id")),
                                 request.form.get("state") == "1")
                msg = "Account updated."
            elif action == "logdel":
                n = users.delete_log(int(request.form.get("user_id")))
                msg = "Deleted " + str(n) + " log rows."
        return render_template_string(USERS_PAGE, user=u, is_admin=_is_admin(),
                                      people=users.list_users(),
                                      recent=users.recent(20),
                                      msg=msg, msg_error=err)

    @app.route("/users/export.csv")
    def users_export():
        u = current_user()
        if not u:
            return redirect(url_for("login"))
        body = users.export_csv(None if u.get("role") == "admin" else u["id"])
        return Response(body, mimetype="text/csv",
                        headers={"Content-Disposition":
                                 "attachment; filename=arkiv-queries.csv"})
