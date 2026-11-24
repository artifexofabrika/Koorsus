"""Document ingest, library listing, matter archiving, favicon."""
import os
import tempfile
from pathlib import Path

from flask import (request, jsonify, render_template_string, redirect,
                   url_for, send_from_directory)
from werkzeug.utils import secure_filename

import config
import matters
from rag import store
from rag.ingest import ingest_file
from templates_html import INGEST_PAGE


def register(app):
    @app.route("/ingest")
    def ingest_page():
        flash = request.args.get("msg")
        flash_error = request.args.get("err") == "1"
        return render_template_string(INGEST_PAGE, flash=flash, flash_error=flash_error)

    def _err(msg):
        return redirect(url_for("ingest_page", msg=msg, err="1"))

    @app.route("/upload", methods=["POST"])
    def upload_route():
        files = request.files.getlist("files")
        if not files or all(not f.filename for f in files):
            return _err("No files selected.")
        uploader = (request.form.get("uploader") or "").strip()
        tag = (request.form.get("tag") or "").strip()
        if not uploader or not tag:
            return _err("Uploader and matter reference are required.")
        ingested = []
        failed = []
        for f in files:
            filename = secure_filename(f.filename)
            if not filename:
                continue
            ext = Path(filename).suffix.lower()
            if ext not in config.SUPPORTED_EXTENSIONS:
                failed.append(filename + " (unsupported " + ext + ")")
                continue
            fd, tmp_path = tempfile.mkstemp(suffix=ext)
            os.close(fd)
            try:
                f.save(tmp_path)
                count = ingest_file(tmp_path, source_name=filename,
                                    extra_metadata={"uploader": uploader, "tag": tag})
                matters.register_matter(tag)
                ingested.append(filename + " (" + str(count) + " chunks)")
            except Exception as e:
                failed.append(filename + " (" + str(e) + ")")
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
        msg = ""
        if ingested:
            msg = ("Ingested " + str(len(ingested)) + " file(s) into matter '" +
                   tag + "': " + "; ".join(ingested) + ". ")
        if failed:
            msg += "Failed: " + "; ".join(failed) + "."
        return redirect(url_for("ingest_page",
                                msg=msg.strip() or "Nothing processed.",
                                err="1" if failed and not ingested else "0"))

    @app.route("/delete", methods=["POST"])
    def delete_route():
        source = (request.form.get("source") or "").strip()
        tag = (request.form.get("tag") or "").strip() or None
        if not source:
            return _err("No document specified.")
        try:
            n = store.delete_source(source, tag)
        except Exception as e:
            return _err("Delete failed: " + str(e))
        if n == 0:
            return _err("Nothing matched " + source + ". Nothing deleted.")
        return redirect(url_for("ingest_page",
                                msg="Deleted " + str(n) + " chunks from " + source + "."))

    @app.route("/documents")
    def documents_route():
        return jsonify(store.stats())

    @app.route("/favicon.ico")
    def favicon():
        return send_from_directory(app.root_path, "favicon.png", mimetype="image/png")

    @app.route("/archive", methods=["POST"])
    def archive_route():
        tag = request.form.get("tag")
        archived = request.form.get("archived") == "1"
        if tag:
            matters.archive_matter(tag, archived)
            msg = "Matter '" + tag + "' " + ("archived" if archived else "restored") + "."
        else:
            msg = "No matter specified."
        return redirect(url_for("ingest_page", msg=msg))
