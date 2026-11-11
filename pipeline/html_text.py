"""Turn email HTML into plain text for the LLM, removing markup only.

- Always decoded as UTF-8 with bad bytes replaced: declared charsets proved
  unreliable.
- Text keeps reading order; block elements become line breaks.
- Data tables keep header, rows and cells as pipe-delimited lines, so every
  value stays next to its label. Layout tables (nested tables, or cells holding
  whole blocks of content) are flattened into reading-order text.
- Link targets are reduced to their host (or the mailto address) in brackets:
  the sender's domain identifies the bank, the tracking query strings don't.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

# A cell longer than this holds a block of content, so its table is layout.
MAX_DATA_CELL_CHARS = 150

DROP_TAGS = {"script", "style", "head", "template", "noscript", "svg", "meta", "link"}
BLOCK_TAGS = {
    "address", "article", "aside", "blockquote", "center", "dd", "div", "dl", "dt",
    "fieldset", "figcaption", "figure", "footer", "form", "h1", "h2", "h3", "h4", "h5",
    "h6", "header", "hr", "main", "nav", "ol", "p", "pre", "section", "ul", "table",
    "tbody", "thead", "tfoot", "tr", "td", "th", "caption", "body", "html",
}

# Marks a blank line (around data tables); every other empty line is dropped.
_GAP = "\x00"

_WS = re.compile(r"[ \t\r\f\v ​　]+")


def load_html(path: Path) -> str:
    return path.read_bytes().decode("utf-8", errors="replace")


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    for t in soup.find_all(DROP_TAGS):
        t.decompose()
    return _tidy(_render(soup))


# --- rendering ---------------------------------------------------------------------


def _render(node) -> str:
    if isinstance(node, NavigableString):
        return _WS.sub(" ", str(node).replace("\n", " "))
    if not isinstance(node, Tag):
        return ""
    name = node.name
    if name == "br":
        return "\n"
    if name == "img":
        alt = (node.get("alt") or "").strip()
        return f" [image: {alt}] " if alt else ""
    if name == "table" and is_data_table(node):
        return f"\n{_GAP}\n" + _render_data_table(node) + f"\n{_GAP}\n"
    inner = "".join(_render(c) for c in node.children)
    if name == "a":
        return inner + _link_note(node.get("href"), inner)
    if name == "li":
        return "\n- " + inner.strip() + "\n"
    if name in BLOCK_TAGS:
        return "\n" + inner + "\n"
    return inner


def _link_note(href: str | None, text: str) -> str:
    if not href:
        return ""
    href = href.strip()
    if href.lower().startswith("mailto:"):
        target = href[7:].split("?", 1)[0]
    else:
        target = urlparse(href).hostname or ""
    if not target or target.lower() in text.lower():
        return ""
    return f" [{target}]"


def _tidy(text: str) -> str:
    out: list[str] = []
    for raw in text.split("\n"):
        line = _WS.sub(" ", raw).strip()
        if line == _GAP:
            if out and out[-1]:
                out.append("")
        elif line:
            out.append(line)
    return "\n".join(out).strip()


# --- tables --------------------------------------------------------------------------


def _own(parent: Tag, names: list[str], owner_name: str) -> list[Tag]:
    """Descendants named ``names`` whose nearest ``owner_name`` ancestor is ``parent``."""
    return [c for c in parent.find_all(names) if c.find_parent(owner_name) is parent]


def _cell_text(cell: Tag) -> str:
    text = "".join(_render(c) for c in cell.children).replace(_GAP, " ").replace("\n", " ")
    return _WS.sub(" ", text).strip()


def _grid(table: Tag) -> list[list[str]]:
    """Rows of cell text, colspans expanded, empty rows and empty columns removed."""
    rows: list[list[str]] = []
    for tr in _own(table, ["tr"], "table"):
        row: list[str] = []
        for cell in _own(tr, ["td", "th"], "tr"):
            row.append(_cell_text(cell))
            try:
                span = int(cell.get("colspan", 1))
            except (TypeError, ValueError):
                span = 1
            row.extend([""] * (min(max(span, 1), 50) - 1))
        if any(row):
            rows.append(row)
    if not rows:
        return []
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    keep = [i for i in range(width) if any(r[i] for r in rows)]
    return [[r[i] for i in keep] for r in rows]


def is_data_table(table: Tag) -> bool:
    if table.find("table") is not None:
        return False
    grid = _grid(table)
    if not grid or len(grid[0]) < 2:
        return False
    if sum(1 for r in grid if sum(1 for c in r if c) >= 2) < 2:
        return False
    return all(len(c) <= MAX_DATA_CELL_CHARS for r in grid for c in r)


def _render_data_table(table: Tag) -> str:
    return "\n".join(" | ".join(r) for r in _grid(table))
