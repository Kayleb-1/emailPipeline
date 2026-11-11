"""Build tiny synthetic email folders on disk for tests."""

from __future__ import annotations

from pathlib import Path


def make_email(
    root: Path,
    name: str,
    html: str | bytes | None = "<html><body><p>Hello</p></body></html>",
    files: dict[str, bytes | str] | None = None,
    dirs: tuple[str, ...] = ("inline", "thumbs"),
) -> Path:
    folder = root / name
    folder.mkdir(parents=True)
    for d in dirs:
        (folder / d).mkdir()
    if html is not None:
        data = html.encode("utf-8") if isinstance(html, str) else html
        (folder / "emailbody.html").write_bytes(data)
    for rel, content in (files or {}).items():
        target = folder / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content.encode("utf-8") if isinstance(content, str) else content)
    return folder
