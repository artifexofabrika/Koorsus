#!/usr/bin/env python3
"""Build a static HTML mirror of the running Myarra app for the public demo.

Fetches every meaningful page from the live app on 127.0.0.1:5002, rewrites
links under /demo/, neutralizes forms, injects a demo banner, and writes a
tour page at the demo root. Stdlib only.
"""
import os
import re
import sqlite3
import sys
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:5002"
DB = "/mnt/lake/myarra.db"
OUT = Path(os.environ.get("DEMO_OUT", Path.home() / "Client-Demo" / "docs" / "demo"))

BANNER = (
    '<div style="position:sticky;top:0;z-index:9999;background:#c0a878;'
    'color:#1a1a1a;padding:0.55rem 1rem;font-family:Georgia,serif;'
    'font-size:0.85rem;text-align:center;box-shadow:0 1px 3px rgba(0,0,0,0.3);">'
    'Static demo of Myarra &middot; <a href="/demo/" '
    'style="color:#1a1a1a;text-decoration:underline;">Tour</a>'
    ' &middot; The live appliance records production in real time.'
    '</div>'
)

FORM_JS = (
    '<script>document.addEventListener("submit",function(e){'
    'e.preventDefault();'
    'alert("Static demo - forms are not functional. The live appliance accepts uploads and edits.");'
    '},true);</script>'
)

TOUR_TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Myarra - Demo Tour</title>
<style>
body{margin:0;background:#1a1a1a;color:#e0e0e0;font-family:Georgia,serif;line-height:1.6}
.wrap{max-width:820px;margin:0 auto;padding:3rem 1.5rem}
h1{color:#c0a878;font-size:2rem;margin:0 0 0.25rem}
.sub{color:#888;font-size:0.95rem;margin-bottom:2.5rem}
h2{color:#c0a878;font-size:1.05rem;text-transform:uppercase;letter-spacing:0.08em;margin-top:2.75rem}
a{color:#c0a878}
.card{display:block;padding:1rem 1.25rem;margin:0.75rem 0;background:#2c2c2c;
      border-left:3px solid #c0a878;border-radius:4px;text-decoration:none;color:#e0e0e0}
.card:hover{background:#333}
.card h3{margin:0 0 0.25rem;color:#c0a878;font-size:1rem}
.card p{margin:0;font-size:0.85rem;color:#b0b0b0}
.small{font-size:0.85rem;color:#888}
ul{columns:2;column-gap:2rem;font-size:0.9rem}
</style></head><body><div class="wrap">
<h1>Myarra</h1>
<div class="sub">A static tour of the live appliance. Every page you click is a
real capture of the running product, taken from the demo dataset. No login, no Jetson.</div>

<h2>The product</h2>
<a class="card" href="/demo/dashboard/"><h3>Live Line Status</h3><p>Five lines, five verticals, one page. What is running right now, against standard.</p></a>
<a class="card" href="/demo/reconciliation/"><h3>Job Reconciliation</h3><p>One row per work order. Units, variance, performance. Click through to any job.</p></a>
<a class="card" href="/demo/changeover/"><h3>Changeover Log</h3><p>Every changeover in the last 30 days, with the components that changed.</p></a>
<a class="card" href="/demo/pdca/"><h3>PDCA Dashboard</h3><p>Active experiments, sorted by priority, with baseline vs current trend.</p></a>
<a class="card" href="/demo/pdca/log/"><h3>PDCA Register</h3><p>Every experiment, active and closed, with its priority score.</p></a>

<h2>Technically curious</h2>
<a class="card" href="/demo/setup/"><h3>Setup</h3><p>Ten CSV templates, one upload form. How a consultant prepares a client appliance before arriving.</p></a>
<a class="card" href="/demo/setup/verify/"><h3>Verify</h3><p>What landed, and anything obviously broken, before the consultant drives to the site.</p></a>
<a class="card" href="/demo/admin/"><h3>Admin</h3><p>User management.</p></a>

<h2>Templates</h2>
<p class="small">The ten onboarding CSVs. In the demo they are static files.</p>
<ul>%s</ul>

<p class="small" style="margin-top:3rem;">The live appliance is an NVIDIA Jetson
Orin on a private network. No data leaves the building. Artifexo Fabrika, Columbus, Ohio.</p>
</div></body></html>"""


def fetch(path):
    with urllib.request.urlopen(BASE + path, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def fetch_bytes(path):
    with urllib.request.urlopen(BASE + path, timeout=30) as r:
        return r.read()


def page_list():
    pages = [
        ("/", "dashboard/index.html"),
        ("/reconciliation?days=30", "reconciliation/index.html"),
        ("/changeover?days=30", "changeover/index.html"),
        ("/pdca", "pdca/index.html"),
        ("/pdca/log", "pdca/log/index.html"),
        ("/setup", "setup/index.html"),
        ("/setup/verify", "setup/verify/index.html"),
        ("/admin", "admin/index.html"),
    ]
    conn = sqlite3.connect(DB)
    for (jn,) in conn.execute("SELECT job_number FROM jobs ORDER BY id"):
        pages.append((f"/job/{jn}", f"job/{jn}/index.html"))
    for (eid,) in conn.execute("SELECT id FROM co_events ORDER BY id"):
        pages.append((f"/changeover/{eid}", f"changeover/{eid}/index.html"))
    for (xid,) in conn.execute("SELECT id FROM experiments ORDER BY id"):
        pages.append((f"/pdca/{xid}", f"pdca/{xid}/index.html"))
        pages.append((f"/pdca/{xid}/edit", f"pdca/{xid}/edit/index.html"))
    conn.close()
    return pages


def rewrite_setup_downloads(html):
    pattern = re.compile(r'(href|src)="/setup/download/([^"]+)"')
    def rep(m):
        attr, name = m.group(1), m.group(2)
        if not name.endswith(".csv"):
            name = name + ".csv"
        return f'{attr}="/demo/setup/download/{name}"'
    return pattern.sub(rep, html)


def rewrite_links(html):
    def sub_attr(attr):
        pattern = re.compile(rf'{attr}="(/[^"]*)"')
        def rep(m):
            p = m.group(1)
            if p.startswith("/demo") or p.startswith("//"):
                return m.group(0)
            return f'{attr}="/demo{p}"'
        return pattern.sub(rep, html)
    html = sub_attr("href")
    html = sub_attr("src")
    html = re.sub(
        r'action="(/[^"]*)"',
        lambda m: m.group(0) if m.group(1).startswith("/demo") else 'action="#"',
        html,
    )
    return html


def neutralize_forms(html):
    html = re.sub(r'<form\b([^>]*)>',
                  lambda m: '<form' + re.sub(r'action="[^"]*"', 'action="#"', m.group(1)) + '>',
                  html)
    if "</body>" in html:
        html = html.replace("</body>", FORM_JS + "</body>", 1)
    else:
        html = html + FORM_JS
    return html


def inject_banner(html):
    m = re.search(r'<body[^>]*>', html)
    if m:
        return html[:m.end()] + BANNER + html[m.end():]
    return BANNER + html


def process_html(html):
    html = rewrite_setup_downloads(html)
    html = rewrite_links(html)
    html = neutralize_forms(html)
    html = inject_banner(html)
    return html


def main():
    if OUT.exists():
        print(f"removing existing {OUT}")
        for child in OUT.iterdir():
            if child.is_dir():
                import shutil; shutil.rmtree(child)
            else:
                child.unlink()
    OUT.mkdir(parents=True, exist_ok=True)

    pages = page_list()
    print(f"crawling {len(pages)} pages")

    for url, relpath in pages:
        dest = OUT / relpath
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            html = fetch(url)
        except Exception as e:
            print(f"  FAIL {url}: {e}")
            continue
        dest.write_text(process_html(html), encoding="utf-8")
        print(f"  ok {url} -> {relpath}")

    # Static assets
    print("copying static assets")
    for asset in ["/static/style.css"]:
        try:
            data = fetch_bytes(asset)
            # Rewrite /static/ -> /demo/static/ inside CSS
            try:
                text = data.decode("utf-8")
                text = text.replace("/static/", "/demo/static/")
                data = text.encode("utf-8")
            except UnicodeDecodeError:
                pass
            dest = OUT / asset.lstrip("/").replace("static/", "static/", 1)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            print(f"  ok {asset}")
        except Exception as e:
            print(f"  FAIL {asset}: {e}")

    # Template CSVs
    print("downloading templates")
    for name in ["lines", "skus", "component_types", "sku_bom", "line_sku_rates",
                 "co_procedures", "co_steps", "jobs", "users", "settings"]:
        try:
            data = fetch_bytes(f"/setup/download/{name}")
            dest = OUT / "setup" / "download" / f"{name}.csv"
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            print(f"  ok {name}.csv")
        except Exception as e:
            print(f"  FAIL {name}: {e}")

    # Tour page
    template_links = "".join(
        f'<li><a href="/demo/setup/download/{n}.csv">{n}.csv</a></li>'
        for n in ["lines", "skus", "component_types", "sku_bom", "line_sku_rates",
                  "co_procedures", "co_steps", "jobs", "users", "settings"]
    )
    (OUT / "index.html").write_text(TOUR_TEMPLATE % template_links, encoding="utf-8")
    print("wrote tour page")

    # .nojekyll at docs root so GitHub Pages serves files verbatim
    docs_root = OUT.parent
    (docs_root / ".nojekyll").touch()
    print(f"touched {docs_root / '.nojekyll'}")

    total = sum(1 for _ in OUT.rglob("*") if _.is_file())
    print(f"DONE. {total} files under {OUT}")


if __name__ == "__main__":
    sys.exit(main())
