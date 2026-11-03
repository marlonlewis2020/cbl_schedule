"""Generate docs/User-Manual.html and docs/User-Manual.docx from user_manual_content.py."""
import sys
from html import escape
from pathlib import Path

from user_manual_content import MANUAL_TITLE, REVISIONS, SECTIONS

DOCS_DIRECTORY = Path(__file__).resolve().parent / "docs"
HTML_PATH = DOCS_DIRECTORY / "User-Manual.html"
DOCX_PATH = DOCS_DIRECTORY / "User-Manual.docx"

CSS = """
body{font-family:Segoe UI,Arial,sans-serif;line-height:1.6;color:#17323d;margin:0;background:#f4f8fa}
main{max-width:920px;margin:0 auto;padding:32px 24px 64px;background:#fff}
h1{font-size:30px;margin:0 0 4px}h2{margin-top:40px;border-bottom:2px solid #087fa8;padding-bottom:6px}
h3{margin-top:24px}nav ol{columns:2;font-size:14px}table{border-collapse:collapse;width:100%;margin:14px 0}
th,td{border:1px solid #c9d8df;padding:8px 10px;text-align:left;vertical-align:top;font-size:14px}
th{background:#e6f3f8}.note{background:#fff7e0;border-left:4px solid #d9a400;padding:10px 14px}
.meta{color:#59717d}
@media print{body{background:#fff}main{max-width:none}}
"""


def revision_section():
    return {
        "id": "revisions",
        "title": "Revision history",
        "blocks": [("table", ["Date", "Change"], [[date, text] for date, text in REVISIONS])],
    }


def all_sections():
    return [*SECTIONS, revision_section()]


def render_blocks_html(blocks):
    parts = []
    for block in blocks:
        kind = block[0]
        if kind == "p":
            parts.append(f"<p>{escape(block[1])}</p>")
        elif kind == "note":
            parts.append(f'<p class="note"><strong>Note:</strong> {escape(block[1])}</p>')
        elif kind == "h3":
            parts.append(f"<h3>{escape(block[1])}</h3>")
        elif kind in ("ul", "ol"):
            items = "".join(f"<li>{escape(item)}</li>" for item in block[1])
            parts.append(f"<{kind}>{items}</{kind}>")
        elif kind == "table":
            head = "".join(f"<th>{escape(cell)}</th>" for cell in block[1])
            rows = "".join(
                "<tr>" + "".join(f"<td>{escape(cell)}</td>" for cell in row) + "</tr>"
                for row in block[2]
            )
            parts.append(f"<table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>")
        else:
            raise ValueError(f"Unknown block type: {kind}")
    return "\n".join(parts)


def build_html():
    sections = all_sections()
    toc = "".join(
        f'<li><a href="#{section["id"]}">{escape(section["title"])}</a></li>' for section in sections
    )
    body = []
    for section in sections:
        body.append(f'<section id="{section["id"]}"><h2>{escape(section["title"])}</h2>')
        body.append(render_blocks_html(section["blocks"]))
        for sub in section.get("subsections", []):
            body.append(f'<section id="{sub["id"]}"><h3 style="font-size:20px">{escape(sub["title"])}</h3>')
            body.append(render_blocks_html(sub["blocks"]))
            body.append("</section>")
        body.append("</section>")
    latest = REVISIONS[0][0]
    return (
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{escape(MANUAL_TITLE)}</title><style>{CSS}</style></head><body><main>"
        f'<h1>{escape(MANUAL_TITLE)}</h1><p class="meta">Last updated {escape(latest)}</p>'
        f"<nav><h2>Contents</h2><ol>{toc}</ol></nav>\n"
        + "\n".join(body)
        + "</main></body></html>\n"
    )


def build_docx(path):
    from docx import Document
    from docx.shared import Pt

    document = Document()
    document.styles["Normal"].font.name = "Calibri"
    document.styles["Normal"].font.size = Pt(11)
    document.core_properties.title = MANUAL_TITLE
    document.add_heading(MANUAL_TITLE, level=0)
    document.add_paragraph(f"Last updated {REVISIONS[0][0]}")

    def add_blocks(blocks):
        for block in blocks:
            kind = block[0]
            if kind == "p":
                document.add_paragraph(block[1])
            elif kind == "note":
                paragraph = document.add_paragraph()
                paragraph.add_run("Note: ").bold = True
                paragraph.add_run(block[1])
            elif kind == "h3":
                document.add_heading(block[1], level=3)
            elif kind == "ul":
                for item in block[1]:
                    document.add_paragraph(item, style="List Bullet")
            elif kind == "ol":
                for number, item in enumerate(block[1], 1):
                    paragraph = document.add_paragraph(f"{number}. {item}")
                    paragraph.paragraph_format.left_indent = Pt(24)
                    paragraph.paragraph_format.first_line_indent = Pt(-14)
            elif kind == "table":
                table = document.add_table(rows=1, cols=len(block[1]))
                table.style = "Table Grid"
                for index, heading in enumerate(block[1]):
                    cell = table.rows[0].cells[index]
                    cell.text = ""
                    cell.paragraphs[0].add_run(heading).bold = True
                for row in block[2]:
                    cells = table.add_row().cells
                    for index, value in enumerate(row):
                        cells[index].text = value
                document.add_paragraph()

    for section in all_sections():
        document.add_heading(section["title"], level=1)
        add_blocks(section["blocks"])
        for sub in section.get("subsections", []):
            document.add_heading(sub["title"], level=2)
            add_blocks(sub["blocks"])
    document.save(path)


def main():
    DOCS_DIRECTORY.mkdir(exist_ok=True)
    HTML_PATH.write_text(build_html(), encoding="utf-8", newline="\n")
    build_docx(DOCX_PATH)
    print(f"Wrote {HTML_PATH}\nWrote {DOCX_PATH}")


if __name__ == "__main__":
    sys.exit(main())
