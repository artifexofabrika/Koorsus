"""User administration and query log page."""

USERS_PAGE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<title>Arkiv - Users</title>
<link rel="stylesheet" href="/static/arkiv.css">
</head><body>
<header class="top">
  <div class="brand">Ar<span class="accent">k</span>iv</div>
  <div class="tagline">Users and queries</div>
  <nav>
    <div class="links"><a href="/">Ask</a><a href="/ingest">Ingest</a><a href="/admin">Admin</a><a href="/users">Users</a></div>
    <a href="/logout" class="signout">Sign out</a>
  </nav>
</header>
<main>
  <h2>Signed in as {{ user.name }}</h2>
  <p class="lede">Role: {{ user.role }}</p>

  {% if msg %}<div class="flash{% if msg_error %} error{% endif %}">{{ msg }}</div>{% endif %}

  <div class="card">
    <h3 style="margin-top:0;color:var(--navy);">Change my PIN</h3>
    <form method="POST" action="/users">
      <input type="hidden" name="action" value="selfpin">
      <div class="field"><label for="current_pin">Current PIN</label>
        <input id="current_pin" type="password" name="current_pin" required autocomplete="current-password"></div>
      <div class="field"><label for="new_pin">New PIN (at least 8 characters)</label>
        <input id="new_pin" type="password" name="new_pin" required autocomplete="new-password"></div>
      <div class="field"><label for="new_pin2">Repeat new PIN</label>
        <input id="new_pin2" type="password" name="new_pin2" required autocomplete="new-password"></div>
      <button type="submit" class="bronze">Update PIN</button>
    </form>
  </div>

  {% if is_admin %}
  <div class="card">
    <h3 style="margin-top:0;color:var(--navy);">Add a user</h3>
    <form method="POST" action="/users">
      <input type="hidden" name="action" value="add">
      <div class="field"><label for="name">Name</label>
        <input id="name" type="text" name="name" required placeholder="Full name"></div>
      <div class="field"><label for="pin">Initial PIN (at least 8 characters)</label>
        <input id="pin" type="password" name="pin" required autocomplete="new-password"></div>
      <div class="field"><label for="role">Role</label>
        <select id="role" name="role"><option value="member">member</option><option value="admin">admin</option></select></div>
      <button type="submit" class="bronze">Create user</button>
    </form>
  </div>

  <div class="card">
    <h3 style="margin-top:0;color:var(--navy);">Accounts</h3>
    <table style="width:100%;border-collapse:collapse;font-size:0.92rem;">
      <tr style="text-align:left;color:var(--muted);font-size:0.8rem;text-transform:uppercase;letter-spacing:0.08em;">
        <th style="padding:0.5rem 0;">Name</th><th>Role</th><th>Status</th><th>Queries</th><th></th>
      </tr>
      {% for p in people %}
      <tr style="border-top:1px solid var(--line);">
        <td style="padding:0.55rem 0;">{{ p.name }}</td>
        <td>{{ p.role }}</td>
        <td>{{ 'active' if p.active else 'inactive' }}</td>
        <td>{{ p.q_count }}</td>
        <td style="text-align:right;">
          <form method="POST" action="/users" style="display:inline;">
            <input type="hidden" name="action" value="active">
            <input type="hidden" name="user_id" value="{{ p.id }}">
            <input type="hidden" name="state" value="{{ '0' if p.active else '1' }}">
            <button type="submit" class="ghost" style="font-size:0.75rem;padding:0.2rem 0.5rem;">{{ 'Deactivate' if p.active else 'Reactivate' }}</button>
          </form>
          <form method="POST" action="/users" style="display:inline;">
            <input type="hidden" name="action" value="logdel">
            <input type="hidden" name="user_id" value="{{ p.id }}">
            <button type="submit" class="ghost" style="font-size:0.75rem;padding:0.2rem 0.5rem;">Delete log</button>
          </form>
        </td>
      </tr>
      {% endfor %}
    </table>
    <p class="lede" style="margin-top:1rem;">Deactivating keeps the account and its history. Deleting the log is separate and deliberate.</p>
  </div>

  <div class="card">
    <h3 style="margin-top:0;color:var(--navy);">Recent questions</h3>
    <p class="lede">Last {{ recent|length }} recorded. <a href="/users/export.csv">Download all as CSV</a></p>
    <div id="recent-answers">
      {% for r in recent %}
      <div class="recent-item" style="border-top:1px solid var(--line);padding:0.55rem 0;font-size:0.9rem;">
        <div style="color:var(--navy);">{{ r.ts }} &middot; {{ r.user_name or '' }}{% if r.matter %} &middot; {{ r.matter }}{% endif %}{% if r.refused %} &middot; refused{% endif %}</div>
        <div style="color:var(--muted);">{{ r.question }}</div>
      </div>
      {% endfor %}
    </div>
    <div style="margin-top:0.8rem;">
      <button class="ghost" onclick="copyRecent()">Copy</button>
      <button class="ghost" onclick="downloadRecent()">Download .txt</button>
      <button class="ghost" onclick="window.print()">Print</button>
    </div>
  </div>
  {% endif %}
</main>
<footer>Artifexo Fabrika &middot; Private &middot; On-premise</footer>
<script>
function recentText() {
  var box = document.getElementById('recent-answers');
  return box ? box.innerText.trim() : '';
}
async function copyRecent() { try { await navigator.clipboard.writeText(recentText()); } catch (e) { alert('Copy failed: ' + e); } }
function downloadRecent() {
  var blob = new Blob([recentText()], {type: 'text/plain;charset=utf-8'});
  var a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'arkiv-queries-' + Date.now() + '.txt';
  a.click();
  URL.revokeObjectURL(a.href);
}
</script>
</body></html>"""

# --- instance skin ---------------------------------------------------------
import brand as _brand

USERS_PAGE = USERS_PAGE.replace("Arkiv - ", _brand.BRAND + " - ")
USERS_PAGE = USERS_PAGE.replace('Ar<span class="accent">k</span>iv',
                                _brand.mark())
