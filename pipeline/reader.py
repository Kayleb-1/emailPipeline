"""Find email folders and check them against the brief's folder definition.

An email folder holds ``emailbody.html`` (required), any ``*.pdf`` files and an
``inline/`` folder of images the HTML references. Anything else is flagged for
another pass: never classified, never silently dropped. Empty or missing
``inline/`` and ``thumbs/`` are normal.
"""

from __future__ import annotations

from pathlib import Path

from pipeline.models import EmailFolder, Flag

HTML_NAME = "emailbody.html"
INLINE_DIR = "inline"
THUMBS_DIR = "thumbs"


def email_dirs(root: Path) -> list[Path]:
    """Every subfolder of the data root, sorted by name."""
    return sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: p.name)


def discover_emails(root: Path) -> list[EmailFolder]:
    """All email folders under ``root``, including ones without HTML (html_path None)."""
    return [read_folder(d)[0] for d in email_dirs(root)]


def _rel(folder: Path, path: Path) -> str:
    return f"{folder.name}/{path.relative_to(folder).as_posix()}"


def _is_pdf(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() == ".pdf"


def read_folder(path: Path) -> tuple[EmailFolder, list[Flag]]:
    source = path.name
    flags: list[Flag] = []
    entries = sorted(path.iterdir(), key=lambda p: p.name)

    html_path = next(
        (p for p in entries if p.is_file() and p.name.lower() == HTML_NAME), None
    )
    if html_path is None:
        flags.append(Flag(source, f"{source}/{HTML_NAME}", "missing_html"))

    pdf_paths = sorted((p for p in entries if _is_pdf(p)), key=lambda p: p.name.casefold())

    inline = path / INLINE_DIR
    inline_dir = inline if inline.is_dir() else None

    expected = {html_path, *pdf_paths, inline_dir, path / THUMBS_DIR}
    for entry in entries:
        if entry not in expected:
            flags.append(Flag(source, _rel(path, entry), "unexpected_file"))

    thumbs = path / THUMBS_DIR
    if thumbs.is_dir():
        for f in sorted(thumbs.rglob("*")):
            if f.is_file():
                flags.append(Flag(source, _rel(path, f), "unexpected_file"))

    folder = EmailFolder(
        source_file=source,
        path=path,
        html_path=html_path,
        pdf_paths=pdf_paths,
        inline_dir=inline_dir,
    )
    return folder, flags
