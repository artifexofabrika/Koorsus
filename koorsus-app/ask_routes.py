"""Ask endpoint, matter listing, and query logging."""
from flask import request, jsonify, render_template_string, current_app

import config
import matters
import users
from auth import current_user
from rag.retrieve import retrieve
from rag.generate import answer
from templates_html import INDEX_PAGE

_AGG = ("how many", "count of", "total number of", "list all", "list every")

_OUTCOME = ("order", "ordered", "ruling", "ruled", "judgment", "judgement",
            "decided", "verdict", "held")

_AGG_MSG = (
    "I answer only from the documents relevant to your question, so I "
    "cannot count or list across the whole library. Use the matter list "
    "or the library view for totals."
)

_NOT_FOUND = "No answer to that question appears in the documents."

_EMPTY = {"sources": [], "matters_found": []}


def _log(q, matter, refused, n):
    try:
        users.log_query(current_user(), matter, q, refused, n)
    except Exception:
        current_app.logger.exception("log write failed")


def _gate(q_lower, matter):
    if not any(w in q_lower for w in _OUTCOME):
        return matter, False
    if isinstance(matter, dict):
        if "$and" in matter:
            matter["$and"].append({"doc_type": "order"})
        else:
            matter = {"$and": [matter, {"doc_type": "order"}]}
    elif matter:
        matter = {"$and": [{"tag": matter}, {"doc_type": "order"}]}
    else:
        matter = {"doc_type": "order"}
    return matter, True


def _answer(q, matter_raw, archived):
    matter = matter_raw

    if matter is None and not archived:
        all_m = matters.get_matters(include_archived=True)
        arch = [m["tag"] for m in all_m if m["status"] == "archived"]
        if arch:
            matter = {"tag": {"$nin": arch}}
    elif isinstance(matter, str):
        matters.touch_matter(matter)

    ql = q.lower()
    if any(p in ql for p in _AGG):
        return dict(_EMPTY, answer=_AGG_MSG), 200, True

    matter, gated = _gate(ql, matter)

    try:
        results = retrieve(q, top_k=config.RETRIEVAL_TOP_K, matter=matter)
    except Exception as e:
        current_app.logger.exception("retrieval failed")
        return dict(_EMPTY, answer="Retrieval failed.",
                    error=str(e)), 503, True

    if not results:
        if isinstance(matter, dict):
            msg = _NOT_FOUND if gated else "No relevant documents in scope."
        elif matter:
            msg = "No documents found in matter '" + str(matter) + "'."
        else:
            msg = "No documents found."
        return dict(_EMPTY, answer=msg), 200, True

    try:
        text, found, cites = answer(q, results)
    except Exception as e:
        current_app.logger.exception("generation failed")
        return dict(_EMPTY,
                    answer="The model did not return a usable answer.",
                    error=str(e)), 503, True

    allowed = {str((r.get("meta") or {}).get("source", "?"))
               .split("[")[0].strip() for r in results}
    cites = [str(c).split("[")[0].strip() for c in cites]
    unknown = [c for c in cites if c not in allowed]

    if unknown:
        current_app.logger.warning("rejected uncited source: %s", unknown)

    cited = sorted(set(cites) & allowed)

    if not found or unknown or not cited:
        return dict(_EMPTY, answer=_NOT_FOUND), 200, True

    tags = sorted({(r.get("meta") or {}).get("tag", "?")
                   for r in results
                   if (r.get("meta") or {}).get("source") in cited})
    payload = {"answer": text, "sources": cited, "matters_found": tags}
    return payload, 200, False


def register(app):
    @app.route("/")
    def home():
        return render_template_string(INDEX_PAGE)

    @app.route("/ask", methods=["POST"])
    def ask_route():
        data = request.get_json(silent=True) or {}
        q = (data.get("question") or "").strip()
        matter = (data.get("matter") or "").strip() or None
        if not q:
            return jsonify(dict(_EMPTY,
                                answer="Please enter a question.")), 400
        payload, status, refused = _answer(
            q, matter, data.get("search_archived", False))
        _log(q, matter, refused, len(payload.get("sources") or []))
        return jsonify(payload), status

    @app.route("/matters")
    def matters_route():
        flag = request.args.get("all") == "1"
        return jsonify({"matters": matters.get_matters(include_archived=flag)})
