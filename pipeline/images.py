"""Resolve the images an email's HTML references to files in its ``inline/`` folder.

References seen in the wild: relative paths (``inline/a.png``), absolute server
paths that end in ``<folder>/inline/<file>``, and ``cid:`` content ids. All are
matched by file name inside this email's ``inline/`` folder. Remote images
(http/https) and ``data:`` URIs are not inline files and are never fetched.

No size filtering and no rules for decorative images: the model decides what
matters. Images the HTML doesn't reference are flagged, not sent.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote, urlparse

from bs4 import BeautifulSoup, Comment, NavigableString

from pipeline.models import EmailFolder, Flag, InlineImage

CONTEXT_CHARS = 200
_SKIP_TEXT_PARENTS = {"script", "style", "head", "title", "template", "noscript"}
_WS = re.compile(r"\s+")
_CSS_URL = re.compile(r"url\(\s*['\"]?([^'\")]+)['\"]?\s*\)", re.I)


def _references(soup: BeautifulSoup) -> list[tuple[str, object]]:
    """(reference, element) pairs in document order: img src and CSS backgrounds."""
    refs: list[tuple[str, object]] = []
    for el in soup.find_all(True):
        if el.name == "img" and el.get("src"):
            refs.append((el["src"].strip(), el))
        if el.get("background"):
            refs.append((el["background"].strip(), el))
        for url in _CSS_URL.findall(el.get("style") or ""):
            refs.append((url.strip(), el))
    return refs


def _is_external(ref: str) -> bool:
    scheme = urlparse(ref).scheme.lower()
    return scheme in {"http", "https", "data"} or ref.startswith("//")


def _candidate_name(ref: str) -> str:
    """The file name a reference points at."""
    if ref.lower().startswith("cid:"):
        return unquote(ref[4:]).split("@", 1)[0]
    path = unquote(urlparse(ref).path)
    return path.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]


def _text_window(el, direction: str) -> str:
    """Up to CONTEXT_CHARS of visible text before or after an element."""
    walker = el.find_all_previous if direction == "before" else el.find_all_next
    parts: list[str] = []
    size = 0
    for s in walker(string=True):
        if isinstance(s, Comment) or (s.parent and s.parent.name in _SKIP_TEXT_PARENTS):
            continue
        text = _WS.sub(" ", str(s)).strip()
        if not text:
            continue
        parts.append(text)
        size += len(text) + 1
        if size >= CONTEXT_CHARS:
            break
    if direction == "before":
        joined = " ".join(reversed(parts))
        return joined[-CONTEXT_CHARS:].strip()
    joined = " ".join(parts)
    return joined[:CONTEXT_CHARS].strip()


def image_context(el) -> str:
    bits = []
    for attr in ("alt", "title"):
        value = _WS.sub(" ", (el.get(attr) or "")).strip()
        if value:
            bits.append(f"{attr}: {value}")
    before = _text_window(el, "before")
    after = _text_window(el, "after")
    if before:
        bits.append(f"before: {before}")
    if after:
        bits.append(f"after: {after}")
    return " | ".join(bits)


def resolve_images(html: str, folder: EmailFolder) -> tuple[list[InlineImage], list[Flag]]:
    source = folder.source_file
    soup = BeautifulSoup(html, "lxml")
    inline_files: dict[str, Path] = {}
    flags: list[Flag] = []
    if folder.inline_dir is not None:
        for p in sorted(folder.inline_dir.iterdir()):
            rel = f"{source}/{folder.inline_dir.name}/{p.name}"
            if p.is_file():
                inline_files[p.name.casefold()] = p
            else:
                flags.append(Flag(source, rel, "unexpected_file"))

    images: list[InlineImage] = []
    used: set[Path] = set()
    missing: set[str] = set()
    for ref, el in _references(soup):
        if not ref or _is_external(ref):
            continue
        name = _candidate_name(ref)
        path = inline_files.get(name.casefold())
        if path is None and ref.lower().startswith("cid:"):
            # Some mailers keep the extension off the content id.
            stem = name.casefold()
            path = next((p for k, p in inline_files.items() if Path(k).stem == stem), None)
        if path is None:
            if ref not in missing:
                missing.add(ref)
                flags.append(Flag(source, ref, "missing_image"))
            continue
        if path in used:
            continue
        used.add(path)
        images.append(InlineImage(path=path, context=image_context(el)))

    for key, p in inline_files.items():
        if p not in used:
            flags.append(Flag(source, f"{source}/{folder.inline_dir.name}/{p.name}",
                              "unreferenced_image"))
    return images, flags
