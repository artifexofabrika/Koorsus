"""HTML templates for the Arkiv web interface.

Extracted verbatim from app.py during the module split. These become
Jinja files under templates/ in the next pass.
"""

LOGIN_PAGE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<title>Arkiv - Sign in</title>
<link rel="stylesheet" href="/static/arkiv.css">
</head><body>
<div class="login-wrap">
  <h1>Ar<span class="accent">k</span>iv</h1>
  <p class="tagline">Your firm's private document assistant</p>
  <div class="card">
    <form method="POST" action="/login">
      <input type="hidden" name="next" value="{{ next }}">
      <div class="field">
        <label for="username">User name</label>
        <input id="username" type="text" name="username" placeholder="Your name" autocomplete="username" autofocus>
      </div>
      <div class="field">
        <label for="pin">Office PIN</label>
        <input id="pin" type="password" name="pin" required placeholder="Enter the office PIN" autocomplete="current-password">
      </div>
      {% if error %}<div class="flash error">{{ error }}</div>{% endif %}
      <button type="submit" class="bronze">Sign in</button>
    </form>
  </div>
  <p class="lede" style="text-align:center;font-size:0.82rem;margin-top:1.5rem;">Artifexo Fabrika &middot; Private &middot; On-premise</p>
</div>
</body></html>"""


INDEX_PAGE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<title>Arkiv - Private Document Assistant</title>
<link rel="stylesheet" href="/static/arkiv.css">
</head><body>
<header class="top">
  <div class="brand">Ar<span class="accent">k</span>iv</div>
  <div class="tagline">Your firm's private document assistant</div>
  <nav>
    <div class="links"><a href="/">Ask</a><a href="/ingest">Ingest</a><a href="/admin">Admin</a><a href="/users">Users</a></div>
    <a href="/logout" class="signout">Sign out</a>
  </nav>
</header>
<main>
  <h2>Ask your firm's documents</h2>
  <p class="lede">Answers come only from documents you have ingested. If the answer is not there, Arkiv says so.</p>

  <div class="scope-row" style="margin-bottom: 0.5rem;">
    <label for="matter">Scope</label>
    <select id="matter">
      <option value="">All matters in the library</option>
    </select>
    <span id="scope-note" class="lede" style="margin:0;"></span>
  </div>
  <div class="scope-row" style="margin-bottom: 1rem;">
    <label style="display:flex;align-items:center;gap:0.4rem;cursor:pointer;font-size:0.9rem;color:var(--muted);margin-left: 4rem;">
      <input type="checkbox" id="show-archived" onchange="loadMatters()" style="width:auto;"> Include archived matters (firm history)
    </label>
  </div>

  <div class="q-row">
    <input id="q" type="text" placeholder="Ask anything about your firm's documents" autocomplete="off" autofocus>
    <button onclick="ask()">Ask</button>
  </div>

  <div class="card" id="answer"><div class="empty">No questions yet.</div></div>

  <details class="recent" id="recent-box">
    <summary>Recent questions (<span id="recent-count">0</span>)</summary>
    <div id="recent-list"></div>
  </details>
</main>
<footer>Artifexo Fabrika &middot; Private &middot; On-premise</footer>
<script>
const RECENT_KEY = 'arkiv_recent';
const MAX_RECENT = 10;

function loadRecent() { try { return JSON.parse(localStorage.getItem(RECENT_KEY) || '[]'); } catch (e) { return []; } }
function saveRecent(list) { localStorage.setItem(RECENT_KEY, JSON.stringify(list.slice(0, MAX_RECENT))); }

async function apiFetch(url, opts) {
  const r = await fetch(url, opts);
  if (r.status === 401) { window.location = '/login'; return null; }
  return r;
}

async function loadMatters() {
  const showArchived = document.getElementById('show-archived').checked;
  const r = await apiFetch('/matters?all=' + (showArchived ? '1' : '0'));
  if (!r) return;
  const data = await r.json();
  const sel = document.getElementById('matter');
  const current = sel.value;
  sel.innerHTML = '<option value="">All matters in the library</option>';
  (data.matters || []).forEach(m => {
    const o = document.createElement('option');
    o.value = m.tag;
    o.textContent = m.tag + ' (' + m.count + ' chunks)';
    sel.appendChild(o);
  });
  // Preserve the selected matter even if the checkbox is unchecked and it drops off the list
  if (current && !Array.from(sel.options).some(o => o.value === current)) {
    const o = document.createElement('option');
    o.value = current;
    o.textContent = current + ' (archived)';
    sel.appendChild(o);
  }
  if (current) sel.value = current;
  const note = document.getElementById('scope-note');
  const total = (data.matters || []).reduce((s, m) => s + m.count, 0);
  note.textContent = total ? total + ' chunks across ' + data.matters.length + ' matter(s)' : 'No documents loaded yet.';
}

async function ask() {
  const input = document.getElementById('q');
  const q = input.value.trim();
  if (!q) return;
  const matter = document.getElementById('matter').value || null;
  const search_archived = document.getElementById('show-archived').checked;
  const box = document.getElementById('answer');
  box.innerHTML = '<div class="q">Q: ' + escapeHtml(q) + '</div>' +
                  '<div class="a">Searching...</div>' +
                  (matter ? '<div class="src">Scoped to: ' + escapeHtml(matter) + '</div>' : '<div class="src">Scoped to: all matters</div>');
  input.value = '';
  try {
    const r = await apiFetch('/ask', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({question: q, matter: matter, search_archived: search_archived})
    });
    if (!r) return;
    const data = await r.json();
    let html = '<div class="q">Q: ' + escapeHtml(q) + '</div>';
    html += '<div class="a">' + escapeHtml(data.answer) + '</div>';
    if (data.sources && data.sources.length) {
      html += '<div class="src">Sources: ' + data.sources.map(escapeHtml).join(', ') + '</div>';
      if (!matter && data.matters_found && data.matters_found.length > 1) {
        html += '<div class="src">Note: this answer drew from ' + data.matters_found.length + ' matters (' + data.matters_found.map(escapeHtml).join(', ') + '). Select one above to scope.';
      }
    }
    html += '<div class="actions">';
    html += '<button class="ghost" onclick="copyCurrent()">Copy</button>';
    html += '<button class="ghost" onclick="downloadCurrent()">Download .txt</button>';
    html += '<button class="ghost" onclick="window.print()">Print</button>';
    html += '</div>';
    box.innerHTML = html;
    addRecent({q: q, a: data.answer, matter: matter, sources: data.sources || []});
  } catch (e) {
    box.innerHTML = '<div class="q">Q: ' + escapeHtml(q) + '</div><div class="a">Request failed: ' + escapeHtml(String(e)) + '</div>';
  }
}

function addRecent(entry) {
  entry.ts = Date.now();
  const list = loadRecent();
  list.unshift(entry);
  saveRecent(list);
  renderRecent();
}

function renderRecent() {
  const list = loadRecent();
  document.getElementById('recent-count').textContent = list.length;
  const box = document.getElementById('recent-list');
  if (!list.length) { box.innerHTML = '<div class="empty">No history yet.</div>'; return; }
  box.innerHTML = '';
  list.forEach((item, idx) => {
    const d = document.createElement('div');
    d.className = 'item';
    d.innerHTML = '<div class="qsmall">Q: ' + escapeHtml(item.q) +
                  ' <button class="ghost" onclick="loadRecentItem(' + idx + ')">View</button></div>' +
                  '<div class="asmall">' + escapeHtml((item.a || '').slice(0, 140)) + '...</div>';
    box.appendChild(d);
  });
}

function loadRecentItem(idx) {
  const list = loadRecent();
  const item = list[idx];
  if (!item) return;
  const box = document.getElementById('answer');
  let html = '<div class="q">Q: ' + escapeHtml(item.q) + '</div>';
  html += '<div class="a">' + escapeHtml(item.a) + '</div>';
  if (item.sources && item.sources.length) {
    html += '<div class="src">Sources: ' + item.sources.map(escapeHtml).join(', ') + '</div>';
  }
  if (item.matter) {
    html += '<div class="src">Scoped to: ' + escapeHtml(item.matter) + '</div>';
  }
  html += '<div class="actions">';
  html += '<button class="ghost" onclick="copyCurrent()">Copy</button>';
  html += '<button class="ghost" onclick="downloadCurrent()">Download .txt</button>';
  html += '<button class="ghost" onclick="window.print()">Print</button>';
  html += '</div>';
  box.innerHTML = html;
}

function currentText() {
  const box = document.getElementById('answer');
  const clone = box.cloneNode(true);
  const actions = clone.querySelector('.actions');
  if (actions) actions.remove();
  return clone.innerText.trim();
}
async function copyCurrent() { try { await navigator.clipboard.writeText(currentText()); } catch (e) { alert('Copy failed: ' + e); } }
function downloadCurrent() {
  const text = currentText();
  const blob = new Blob([text], {type: 'text/plain;charset=utf-8'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'arkiv-answer-' + Date.now() + '.txt';
  a.click();
  URL.revokeObjectURL(a.href);
}
function escapeHtml(s) { return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
document.getElementById('q').addEventListener('keydown', e => { if (e.key === 'Enter') ask(); });
loadMatters();
renderRecent();
</script>
</body></html>"""


INGEST_PAGE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<title>Arkiv - Ingest Documents</title>
<link rel="stylesheet" href="/static/arkiv.css">
</head><body>
<header class="top">
  <div class="brand">Ar<span class="accent">k</span>iv</div>
  <div class="tagline">Ingest documents</div>
  <nav>
    <div class="links"><a href="/">Ask</a><a href="/ingest">Ingest</a><a href="/admin">Admin</a><a href="/users">Users</a></div>
    <a href="/logout" class="signout">Sign out</a>
  </nav>
</header>
<main>
  <h2>Add documents</h2>
  <p class="lede">Every document is tagged with an uploader and a matter reference so citations are accurate.</p>
  {% if flash %}<div class="flash{% if flash_error %} error{% endif %}">{{ flash }}</div>{% endif %}
  <div class="card">
    <form method="POST" action="/upload" enctype="multipart/form-data">
      <div class="field">
        <label for="file">Document files (select one or more)</label>
        <input id="file" type="file" name="files" multiple required accept=".txt,.md,.pdf,.docx,.odt">
      </div>
      <div class="field">
        <label for="uploader">Uploaded by</label>
        <input id="uploader" type="text" name="uploader" required placeholder="Your name">
      </div>
      <div class="field">
        <label for="tag">Matter reference or category</label>
        <input id="tag" type="text" name="tag" required placeholder="e.g. 2026-0142 Henderson; Contract">
      </div>
      <button type="submit" class="bronze">Upload and ingest</button>
    </form>
  </div>
  <details style="margin-top:2rem;">
    <summary style="cursor:pointer;color:var(--muted);font-size:0.9rem;text-transform:uppercase;letter-spacing:0.08em;">Current library</summary>
    <div class="card" id="library" style="margin-top:0.75rem;"><span class="empty">Loading...</span></div>
  </details>
</main>
<footer>Artifexo Fabrika &middot; Private &middot; On-premise</footer>
<script>
async function apiFetch(url, opts) {
  const r = await fetch(url, opts);
  if (r.status === 401) { window.location = '/login'; return null; }
  return r;
}
function prefill() {
  try {
    const u = localStorage.getItem('arkiv_uploader');
    const t = localStorage.getItem('arkiv_tag');
    if (u) document.getElementById('uploader').value = u;
    if (t) document.getElementById('tag').value = t;
  } catch (e) {}
}
document.querySelector('form').addEventListener('submit', () => {
  try {
    localStorage.setItem('arkiv_uploader', document.getElementById('uploader').value);
    localStorage.setItem('arkiv_tag', document.getElementById('tag').value);
  } catch (e) {}
});
async function loadLibrary() {
  const r = await apiFetch('/documents');
  if (!r) return;
  const data = await r.json();
  const el = document.getElementById('library');
  const total = data.total_chunks || 0;
  if (total === 0) { el.innerHTML = '<span class="empty">No documents yet.</span>'; return; }
  let html = '<p class="lede"><strong>' + total + '</strong> chunks.</p><ul>';
  try {
    const r2 = await apiFetch('/matters?all=1');
    if (!r2) throw new Error('Failed to load matters');
    const mdata = await r2.json();
    (mdata.matters || []).sort((a,b) => a.tag.localeCompare(b.tag)).forEach(m => {
      const isArch = m.status === 'archived';
      const label = isArch ? 'Restore' : 'Archive';
      const val = isArch ? '0' : '1';
      const color = isArch ? '#4f7c3a' : '#a33';
      html += '<li style="margin-bottom:0.5rem;">' + m.tag + ' - ' + m.count + ' chunks ';
      html += '<form method="POST" action="/archive" style="display:inline;"><input type="hidden" name="tag" value="' + m.tag.replace(/"/g, '&quot;') + '"><input type="hidden" name="archived" value="' + val + '"><button type="submit" style="font-size:0.75rem;padding:0.2rem 0.5rem;background:transparent;color:' + color + ';border:1px solid ' + color + ';border-radius:3px;cursor:pointer;margin-left:0.5rem;">' + label + '</button></form>';
      html += '</li>';
    });
  } catch (e) {
    html += '<li style="color:red;font-weight:bold;">Error loading matters: ' + e.message + '</li>';
  }
  html += '</ul>';
  el.innerHTML = html;
}
prefill();
loadLibrary();
</script>
</body></html>"""


ADMIN_PAGE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<title>Arkiv - Admin</title>
<link rel="stylesheet" href="/static/arkiv.css">
</head><body>
<header class="top">
  <div class="brand">Ar<span class="accent">k</span>iv</div>
  <div class="tagline">Administrator</div>
  <nav>
    <div class="links"><a href="/">Ask</a><a href="/ingest">Ingest</a><a href="/admin">Admin</a><a href="/users">Users</a></div>
    <a href="/logout" class="signout">Sign out</a>
  </nav>
</header>
<main>
  <h2>Administrator controls</h2>
  <p class="lede">These actions affect the whole appliance.</p>

  {% if msg %}
  <div class="flash{% if msg_error %} error{% endif %}" style="white-space: pre-wrap; font-family: monospace; font-size: 0.85rem; max-height: 300px; overflow-y: auto;">{{ msg }}</div>
  {% endif %}

  <div class="card">
    <h3 style="margin-top:0;color:var(--navy);">Backup status</h3>
    <p style="font-size:0.9rem;color:var(--muted);font-family:monospace;">{{ last_verify }}</p>
    <div style="display:flex;gap:1rem;margin-top:1rem;">
      <form method="POST" action="/admin/backup" data-confirm="Run a backup now?">
        <button type="submit" class="bronze">Run Backup Now</button>
      </form>
      <form method="POST" action="/admin/verify" data-confirm="Run a restore rehearsal now? This may take a minute.">
        <button type="submit" class="ghost">Verify Backup</button>
      </form>
    </div>
  </div>

  <div class="card">
    <h3 style="margin-top:0;color:var(--navy);">Restore</h3>
    <p style="font-size:0.9rem;color:var(--muted);">Restores the latest backup. The current library will be moved aside, not deleted.</p>
    <form method="POST" action="/admin/restore" data-confirm="Restore from the latest backup?">
      <button type="submit" class="ghost">Restore Latest Backup</button>
    </form>
  </div>

  <div class="card" style="border-color:#a33;">
    <h3 style="margin-top:0;color:#a33;">Factory Reset</h3>
    <p style="font-size:0.9rem;color:var(--muted);">Removes all documents from the live library. The current index is moved aside, not deleted.</p>
    <form method="POST" action="/admin/reset" data-confirm="Are you sure you want to remove all documents? This cannot be easily undone.">
      <button type="submit" style="background:#a33;color:white;">Reset Library</button>
    </form>
  </div>
<div class="card">
  <h3 style="margin-top:0;color:var(--navy);">Backup to USB</h3>
  <p style="font-size:0.9rem;color:var(--muted);">
    Copies the newest archive to a mounted USB stick, or restores
    from one. The archive stays encrypted either way.
  </p>
  <div style="display:flex;gap:1rem;">
    <form method="POST" action="/admin/export-usb"
          data-confirm="Copy the newest backup to the USB?">
      <button type="submit" class="bronze">Copy to USB</button>
    </form>
    <form method="POST" action="/admin/import-usb"
          data-confirm="Restore from the archive on the USB?">
      <button type="submit" class="ghost">Restore from USB</button>
    </form>
  </div>
  <p style="font-size:0.85rem;color:var(--muted);">
  <p style="font-size:0.9rem;color:var(--muted);">
    Stick: {% if usb_mounted %}mounted and ready
    {% else %}not inserted{% endif %}
  </p>
  <form method="POST" action="/admin/eject-usb"
        data-confirm="Unmount the USB so it can be removed safely?">
    <button type="submit" class="ghost">Eject USB</button>
  </form>
    Smoke: {{ smoke_status }}
  </p>
</div>

</main>
<footer>Artifexo Fabrika &middot; Private &middot; On-premise</footer>

<div id="confirm-bar" style="display:none; position:fixed; left:0; right:0; bottom:0; background:#0a1e3a; border-top:3px solid #b08d57; color:#fff; padding:1rem 1.5rem; z-index:50; text-align:center;">
  <span id="confirm-text" style="margin-right:1rem;"></span>
  <button id="confirm-yes" class="bronze" style="margin-right:0.5rem;">Confirm</button>
  <button id="confirm-no" class="ghost" style="background:#fff;">Cancel</button>
</div>
<script>
(function () {
  var pending = null;
  var bar = document.getElementById('confirm-bar');
  document.querySelectorAll('form[data-confirm]').forEach(function (f) {
    f.addEventListener('submit', function (e) {
      if (f.dataset.confirmed === '1') return;
      e.preventDefault();
      pending = f;
      document.getElementById('confirm-text').textContent = f.dataset.confirm;
      bar.style.display = 'block';
    });
  });
  document.getElementById('confirm-yes').addEventListener('click', function () {
    if (!pending) return;
    pending.dataset.confirmed = '1';
    bar.style.display = 'none';
    pending.submit();
  });
  document.getElementById('confirm-no').addEventListener('click', function () {
    pending = null;
    bar.style.display = 'none';
  });
})();
</script>
</body></html>"""

# --- instance skin ---------------------------------------------------------
import brand as _brand


def _skin(t):
    t = t.replace('Ar<span class="accent">k</span>iv', _brand.mark())
    t = t.replace("Your firm's private document assistant", _brand.TAGLINE)
    t = t.replace("Arkiv - ", _brand.BRAND + " - ")
    return t


LOGIN_PAGE = _skin(LOGIN_PAGE)
INDEX_PAGE = _skin(INDEX_PAGE)
INGEST_PAGE = _skin(INGEST_PAGE)
ADMIN_PAGE = _skin(ADMIN_PAGE)

_PHRASES = [
    ("Ask your firm's documents", "Ask your plant's documents"),
    ("All matters in the library", "All areas in the library"),
    ("Include archived matters (firm history)",
     "Include archived areas (plant history)"),
    ("Matter reference or category", "Area reference or category"),
    ("matter reference", "area reference"),
    ("Office PIN", "Site PIN"),
    ("firm's", "plant's"),
    ("Your firm", "Your plant"),
]


def _skinquote(t):
    for a, b in _PHRASES:
        t = t.replace(a, b)
    return t


if _brand.BRAND != "Arkiv":
    LOGIN_PAGE = _skinquote(LOGIN_PAGE)
    INDEX_PAGE = _skinquote(INDEX_PAGE)
    INGEST_PAGE = _skinquote(INGEST_PAGE)
    ADMIN_PAGE = _skinquote(ADMIN_PAGE)


def _brandsays(t):
    return t.replace("Arkiv says so", _brand.BRAND + " says so")


LOGIN_PAGE = _brandsays(LOGIN_PAGE)
INDEX_PAGE = _brandsays(INDEX_PAGE)
INDEX_PAGE = INDEX_PAGE.replace("</body></html>",
    '<script src="/static/recent.js"></script></body></html>', 1)
INGEST_PAGE = _brandsays(INGEST_PAGE)
ADMIN_PAGE = _brandsays(ADMIN_PAGE)
