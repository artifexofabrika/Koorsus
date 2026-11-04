"""Convert the outreach markdown files to PDF. Tries weasyprint, falls
back to xhtml2pdf if weasyprint is unavailable or fails."""
import sys
from pathlib import Path
import markdown

HERE = Path(__file__).parent
CSS = (HERE / "outreach.css").read_text()

FILES = [
    ("cv.md",            "Randy-Wolf-CV.pdf"),
    ("odoo-advisory.md", "Odoo-Manufacturing-Advisory.pdf"),
    ("reperio-note.md",  "Reperio-Application-Note.pdf"),
]

HTML_TEMPLATE = """<!doctype html>
<html><head><meta charset="utf-8"><style>{css}</style></head>
<body>{body}</body></html>"""


def to_html(md_path: Path) -> str:
    body = markdown.markdown(
        md_path.read_text(),
        extensions=["extra", "sane_lists", "smarty"],
    )
    return HTML_TEMPLATE.format(css=CSS, body=body)


def try_weasyprint(html: str, out: Path) -> bool:
    try:
        from weasyprint import HTML
    except Exception as e:
        print(f"  weasyprint unavailable: {e}")
        return False
    try:
        HTML(string=html, base_url=str(HERE)).write_pdf(str(out))
        return True
    except Exception as e:
        print(f"  weasyprint failed at render: {e}")
        return False


def try_xhtml2pdf(html: str, out: Path) -> bool:
    try:
        from xhtml2pdf import pisa
    except Exception as e:
        print(f"  xhtml2pdf unavailable: {e}")
        return False
    try:
        with open(out, "wb") as f:
            status = pisa.CreatePDF(html, dest=f)
        if status.err:
            print(f"  xhtml2pdf reported {status.err} errors")
            return False
        return True
    except Exception as e:
        print(f"  xhtml2pdf failed: {e}")
        return False


def main():
    engine_used = None
    for src, dst in FILES:
        src_path = HERE / src
        out_path = HERE / dst
        if not src_path.exists():
            print(f"MISSING: {src}")
            continue
        html = to_html(src_path)
        print(f"converting {src} -> {dst}")
        if engine_used != "xhtml2pdf":
            if try_weasyprint(html, out_path):
                engine_used = "weasyprint"
                print(f"  ok ({engine_used})")
                continue
            else:
                engine_used = "xhtml2pdf"
        if try_xhtml2pdf(html, out_path):
            print(f"  ok ({engine_used})")
        else:
            print(f"  FAILED both engines on {src}")
            return 1
    print(f"\nDONE using {engine_used}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
