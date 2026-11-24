"""Administrator actions: backup, verify, restore, reset, USB."""
import datetime
import os
import subprocess

from flask import render_template_string

from rag import store
from templates_html import ADMIN_PAGE

SCRIPT_DIR = os.environ.get("ARKIV_SCRIPT_DIR",
                       "/usr/local/sbin/arkiv")
INDEX_PATH = os.environ.get("ARKIV_INDEX_PATH",
                       "/mnt/lake/arkiv_index")
VERIFY_STATUS = os.environ.get("ARKIV_VERIFY_STATUS",
                           "/var/log/arkiv-verify.status")
SMOKE_STATUS = os.environ.get("ARKIV_SMOKE_STATUS",
                          "/var/log/arkiv-smoke.status")


def _run_script(name, timeout=300):
    path = os.path.join(SCRIPT_DIR, name)
    try:
        proc = subprocess.run(["sudo", "-n", path],
                              capture_output=True, text=True, timeout=timeout)
        out = (proc.stdout + "\n" + proc.stderr).strip()
        return proc.returncode == 0, out
    except Exception as e:
        return False, str(e)


def _read(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return f.read().strip()
        except Exception:
            pass
    return default


def _render(msg=None, msg_error=False):
    return render_template_string(
        ADMIN_PAGE,
        last_verify=_read(VERIFY_STATUS, "No verification has run yet."),
        smoke_status=_read(SMOKE_STATUS, "No smoke run recorded yet."),
        usb_mounted=os.path.ismount("/mnt/usb"),
        msg=msg,
        msg_error=msg_error)


def _admin_reset():
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    old = INDEX_PATH + ".reset." + ts
    if os.path.exists(INDEX_PATH):
        os.rename(INDEX_PATH, old)
    os.makedirs(INDEX_PATH)
    subprocess.run(["sudo", "-n", "chown", "jeeves:jeeves", INDEX_PATH])
    store.reload()
    return "Reset complete. Previous index moved to " + old + "."


def _admin_restore():
    path = os.path.join(SCRIPT_DIR, "restore-index.sh")
    res = subprocess.run(["sudo", "-n", path],
                         capture_output=True, text=True, timeout=600)
    out = (res.stdout + "\n" + res.stderr).strip()
    if res.returncode != 0:
        raise Exception("Restore failed:\n" + out)
    store.reload()
    return out


def register(app):
    @app.route("/admin", methods=["GET"])
    def admin_page():
        return _render()

    @app.route("/admin/backup", methods=["POST"])
    def admin_backup():
        ok, out = _run_script("backup.sh")
        head = "Backup complete.\n" if ok else "Backup failed.\n"
        return _render(head + out, not ok)

    @app.route("/admin/verify", methods=["POST"])
    def admin_verify():
        ok, out = _run_script("verify-backup.sh")
        head = "Verification complete.\n" if ok else "Verification failed.\n"
        return _render(head + out, not ok)

    @app.route("/admin/export-usb", methods=["POST"])
    def admin_export_usb():
        ok, out = _run_script("export-usb.sh")
        head = "Copied to USB.\n" if ok else "USB copy failed.\n"
        return _render(head + out, not ok)

    @app.route("/admin/import-usb", methods=["POST"])
    def admin_import_usb():
        ok, out = _run_script("import-usb.sh", timeout=600)
        if ok:
            store.reload()
        head = "Restored from USB.\n" if ok else "USB restore failed.\n"
        return _render(head + out, not ok)

    @app.route("/admin/eject-usb", methods=["POST"])
    def admin_eject_usb():
        ok, out = _run_script("usb-eject.sh")
        head = "USB ejected.\n" if ok else "Eject failed.\n"
        return _render(head + out, not ok)

    @app.route("/admin/restore", methods=["POST"])
    def admin_restore():
        try:
            return _render(_admin_restore())
        except Exception as e:
            return _render("Restore failed: " + str(e), True)

    @app.route("/admin/reset", methods=["POST"])
    def admin_reset():
        try:
            return _render(_admin_reset())
        except Exception as e:
            return _render("Reset failed: " + str(e), True)
