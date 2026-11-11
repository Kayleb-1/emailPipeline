"""Full text from each PDF attachment.

Charts and images inside PDFs are not interpreted (a deliberate scope limit).
A PDF that yields little or no text, or can't be read, comes back with a
warning for the log instead of crashing the run.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from pypdf import PdfReader

# Below this many non-space characters per page the PDF is probably scanned or
# image-only, so its text can't be trusted to carry the content.
MIN_CHARS_PER_PAGE = 100

logging.getLogger("pypdf").setLevel(logging.ERROR)

_SPACES = re.compile(r"[ \t ]+")
_BLANKS = re.compile(r"\n{3,}")


def _clean(text: str) -> str:
    text = _SPACES.sub(" ", text.replace("\r\n", "\n").replace("\r", "\n"))
    lines = [line.strip() for line in text.split("\n")]
    return _BLANKS.sub("\n\n", "\n".join(lines)).strip()


def extract_pdf_text(path: Path) -> tuple[str, str | None]:
    """Return (text, warning). Warning is None when the PDF read cleanly."""
    try:
        reader = PdfReader(path)
        if reader.is_encrypted:
            reader.decrypt("")
        pages = [p.extract_text() or "" for p in reader.pages]
    except Exception as exc:  # pypdf raises many types on malformed files
        return "", f"{path.name}: could not read PDF ({type(exc).__name__}: {exc})"

    text = _clean("\n\n".join(pages))
    n_pages = max(len(pages), 1)
    chars = len(re.sub(r"\s", "", text))
    if chars < MIN_CHARS_PER_PAGE * n_pages:
        return text, (
            f"{path.name}: little or no text ({chars} chars over {len(pages)} pages); "
            "may be scanned or image-only"
        )
    return text, None
