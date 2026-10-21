"""
app.py — Flask web interface for the Jeeves RAG appliance.

Routes:
  GET  /             — chat interface
  POST /ask          — {"question": "..."} -> {"answer": "...", "sources": [...]}
  POST /upload       — multipart file upload; ingests into the collection
  POST /clear        — wipes the collection (new session)
  GET  /documents    — current collection inventory
"""

import os
import tempfile
from pathlib import Path

from flask import Flask, request, jsonify, render_template_string
from werkzeug.utils import secure_filename

import config
from rag.retrieve import retrieve
from rag.generate import answer
from rag.ingest import ingest_file
from rag import store

app = Flask(__name__)

PAGE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Koorsus — Private Assistant</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 820px; margin: 2rem auto;
         padding: 0 1rem; background: #f7f7f5; color: #222; }
  h1 { font-weight: 500; letter-spacing: -0.01em; margin-bottom: 0.2rem; }
  .sub { color: #666; margin-top: 0; }
  .toolbar { display: flex; justify-content: space-between; align-items: center;
             background: #fff; border: 1px solid #ddd; border-radius: 8px;
             padding: 0.75rem 1rem; margin: 1rem 0; font-size: 0.9rem; }
  .toolbar .docs { color: #555; }
  .toolbar .docs strong { color: #222; }
  #log { background: #fff; border: 1px solid #ddd; border-radius: 8px;
         padding: 1rem; min-height: 320px; max-height: 520px; overflow-y: auto; }
  .q { font-weight: 600; margin-top: 1rem; }
  .a { white-space: pre-wrap; margin: 0.5rem 0 0.25rem 0; }
  .src { font-size: 0.82rem; color: #777; margin-bottom: 0.5rem; }
  .row { display: flex; gap: 0.5rem; margin-top: 1rem; }
  input[type=text] { flex: 1; padding: 0.65rem; font-size: 1rem;
                     border: 1px solid #ccc; border-radius: 6px; }
  button { padding: 0.65rem 1.1rem; font-size: 0.95rem; border: 0;
           border-radius: 6px; background: #2a2a2a; color: #fff;
           cursor: pointer; }
  button:hover { background: #444; }
  button.secondary { background: #fff; color: #444; border: 1px solid #ccc; }
  button.secondary:hover { background: #f0f0f0; }
  .upload { margin-top: 1rem; font-size: 0.9rem; color: #555;
            display: flex; align-items: center; gap: 0.5rem; }
  .notice { font-size: 0.85rem; color: #666; margin-top: 0.5rem; }
</style>
</head>
<body>
  <h1>Koorsus</h1>
  <p class="sub">Private assistant. Answers only from your documents.</p>

  <div class="toolbar">
    <div class="docs" id="docs">Loading…</div>
    <button class="secondary" onclick="clearAll()">Start New Session</button>
  </div>

  <div id="log"></div>

  <div class="row">
    <input id="q" type="text" placeholder="Ask a question about the documents..."
           autocomplete="off" autofocus>
    <button onclick="ask()">Ask</button>
  </div>

  <div class="upload">
    <input id="file" type="file">
    <button class="secondary" onclick="upload()">Upload &amp; ingest</button>
  </div>

<script>
async function refreshDocs() {
  const r = await fetch('/documents');
  const data = await r.json();
  const el = document.getElementById('docs');
  const total = data.total_chunks || 0;
  const sources = data.sources || {};
  const names = Object.keys(sources);
  if (total === 0) {
    el.innerHTML = 'No documents loaded.';
  } else {
    const list = names.map(n => `${n} (${sources[n]})`).join(', ');
    el.innerHTML = `<strong>${total} chunks</strong> from ${names.length} document(s): ${list}`;
  }
}

async function ask() {
  const input = document.getElementById('q');
  const q = input.value.trim();
  if (!q) return;
  const log = document.getElementById('log');
  log.innerHTML += `<div class="q">Q: ${escapeHtml(q)}</div>`;
  input.value = '';
  const r = await fetch('/ask', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({question: q})
  });
  const data = await r.json();
  log.innerHTML += `<div class="a">${escapeHtml(data.answer)}</div>`;
  if (data.sources && data.sources.length) {
    log.innerHTML += `<div class="src">Sources: ${escapeHtml(data.sources.join(', '))}</div>`;
  }
  log.scrollTop = log.scrollHeight;
}

async function upload() {
  const f = document.getElementById('file').files[0];
  if (!f) return alert('Choose a file first.');
  const fd = new FormData();
  fd.append('file', f);
  const log = document.getElementById('log');
  log.innerHTML += `<div class="src">Uploading ${escapeHtml(f.name)}…</div>`;
  const r = await fetch('/upload', { method: 'POST', body: fd });
  const data = await r.json();
  if (data.error) {
    log.innerHTML += `<div class="src">Error: ${escapeHtml(data.error)}</div>`;
  } else {
    log.innerHTML += `<div class="src">Ingested ${escapeHtml(data.filename)}: ${data.chunks} chunks</div>`;
  }
  log.scrollTop = log.scrollHeight;
  document.getElementById('file').value = '';
  refreshDocs();
}

async function clearAll() {
  if (!confirm('Clear all documents and start a new session?')) return;
  await fetch('/clear', { method: 'POST' });
  document.getElementById('log').innerHTML = '';
  refreshDocs();
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',
                                        '"':'&quot;',"'":'&#39;'}[c]));
}

document.getElementById('q').addEventListener('keydown', e => {
  if (e.key === 'Enter') ask();
});

refreshDocs();
</script>
</body>
</html>"""


@app.route("/")
def home():
    return render_template_string(PAGE)


@app.route("/ask", methods=["POST"])
def ask_route():
    data = request.get_json(force=True)
    q = (data.get("question") or "").strip()
    if not q:
        return jsonify({"answer": "Please enter a question.", "sources": []}), 400
    results = retrieve(q, top_k=config.RETRIEVAL_TOP_K)
    if not results:
        return jsonify({"answer": "No documents are loaded.", "sources": []})
    ans = answer(q, results)
    _markers = ("not in the provided context", "not mentioned", "not in the documents", "does not contain", "no information about")
    refused = any(m in ans.lower() for m in _markers)
    sources = [] if refused else sorted({(r.get("meta") or {}).get("source", "?") for r in results})
    return jsonify({"answer": ans, "sources": sources})


@app.route("/upload", methods=["POST"])
def upload_route():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    f = request.files["file"]
    filename = secure_filename(f.filename)
    if not filename:
        return jsonify({"error": "Empty filename"}), 400
    ext = Path(filename).suffix.lower()
    if ext not in config.SUPPORTED_EXTENSIONS:
        return jsonify({"error": f"Unsupported format: {ext}"}), 400

    fd, tmp_path = tempfile.mkstemp(suffix=ext)
    os.close(fd)
    try:
        f.save(tmp_path)
        count = ingest_file(tmp_path, source_name=filename)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
    return jsonify({"filename": filename, "chunks": count})


@app.route("/clear", methods=["POST"])
def clear_route():
    store.reset_collection()
    return jsonify({"ok": True})


@app.route("/documents", methods=["GET"])
def documents_route():
    return jsonify(store.stats())


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
