"""Read-only SQLite index for the dashboard, derived from classified_emails.json.

The JSON stays the deliverable and the source of truth. This index adds what
analysts need to find research: FTS5 full-text search over title, bank,
companies, industries, email body and PDF text, and join tables so filters can
show counts per value. It is rebuilt from scratch on every run and never edited.
Body and PDF text come from the same extraction the classifier used.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from pipeline import taxonomy as tx
from pipeline.html_text import html_to_text, load_html
from pipeline.models import EmailRecord
from pipeline.pdfs import extract_pdf_text
from pipeline.reader import read_folder

SCHEMA = (Path(__file__).parent / "schema.sql").read_text(encoding="utf-8")


class IndexBuildError(ValueError):
    """classified_emails.json can't be indexed (bad shape or record)."""


def load_records(json_path: Path) -> list[EmailRecord]:
    try:
        raw = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise IndexBuildError(f"{json_path} is not valid JSON: {exc}") from exc
    if not isinstance(raw, list):
        raise IndexBuildError(f"{json_path} must hold a list of records")
    records: list[EmailRecord] = []
    seen: set[str] = set()
    for i, item in enumerate(raw):
        try:
            record = EmailRecord.model_validate(item)
        except ValidationError as exc:
            name = item.get("source_file", f"#{i}") if isinstance(item, dict) else f"#{i}"
            raise IndexBuildError(f"record {name} breaks the ten-field schema: {exc}") from exc
        if record.source_file in seen:
            raise IndexBuildError(f"duplicate source_file {record.source_file!r}")
        seen.add(record.source_file)
        records.append(record)
    return records


def email_texts(data_dir: Path, source_file: str) -> tuple[str, str, list[str]]:
    """(body text, PDF text, warnings) for one email folder."""
    path = data_dir / source_file
    if not path.is_dir():
        return "", "", [f"{source_file}: folder not found in {data_dir}"]
    folder, _ = read_folder(path)
    warnings: list[str] = []
    body = html_to_text(load_html(folder.html_path)) if folder.html_path else ""
    if not folder.html_path:
        warnings.append(f"{source_file}: no emailbody.html")
    pdf_parts = []
    for pdf in folder.pdf_paths:
        text, warning = extract_pdf_text(pdf)
        pdf_parts.append(text)
        if warning:
            warnings.append(f"{source_file}: {warning}")
    return body, "\n\n".join(pdf_parts), warnings


def _insert(conn: sqlite3.Connection, r: EmailRecord, body: str, pdf_text: str) -> None:
    conn.execute(
        "INSERT INTO emails VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (r.source_file, r.folder_name, r.bank, r.date, r.market_wrap, r.primary_asset_tag,
         int(bool(r.pdf_attachment)), json.dumps(r.to_json_dict(), ensure_ascii=False)),
    )
    conn.executemany(
        "INSERT INTO email_asset_tags VALUES (?, ?, ?, ?)",
        [(r.source_file, t, tx.SUB_TO_PARENT.get(t), int(t == r.primary_asset_tag))
         for t in r.asset_tags],
    )
    conn.executemany("INSERT OR IGNORE INTO email_companies VALUES (?, ?)",
                     [(r.source_file, c) for c in r.companies_mentioned])
    conn.executemany(
        "INSERT INTO email_industries VALUES (?, ?, ?)",
        [(r.source_file, s, s.split(tx.INDUSTRY_SEPARATOR)[0] if tx.INDUSTRY_SEPARATOR in s else None)
         for s in r.industry_subindustry],
    )
    conn.executemany("INSERT INTO email_pdfs VALUES (?, ?, ?)",
                     [(r.source_file, f, i) for i, f in enumerate(r.pdf_attachment or [])])
    conn.execute(
        "INSERT INTO email_fts VALUES (?, ?, ?, ?, ?, ?, ?)",
        (r.source_file, r.folder_name, r.bank, "; ".join(r.companies_mentioned),
         "; ".join(r.industry_subindustry), body, pdf_text),
    )


def build_index(json_path: Path, data_dir: Path, db_path: Path) -> dict:
    """Rebuild the index from scratch. Returns a summary with any text warnings."""
    records = load_records(json_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=db_path.parent, prefix=f".{db_path.name}.", suffix=".tmp")
    os.close(fd)
    warnings: list[str] = []
    conn = sqlite3.connect(tmp)
    try:
        conn.executescript(SCHEMA)
        with conn:
            for r in records:
                body, pdf_text, w = email_texts(data_dir, r.source_file)
                warnings.extend(w)
                _insert(conn, r, body, pdf_text)
            meta = {
                "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "source_json": str(json_path),
                "source_sha256": hashlib.sha256(json_path.read_bytes()).hexdigest(),
                "data_dir": str(data_dir.resolve()),
                "records": str(len(records)),
            }
            conn.executemany("INSERT INTO meta VALUES (?, ?)", meta.items())
        conn.execute("INSERT INTO email_fts(email_fts) VALUES ('optimize')")
        conn.commit()
    except BaseException:
        conn.close()
        os.unlink(tmp)
        raise
    conn.close()
    os.replace(tmp, db_path)
    return {"records": len(records), "warnings": warnings, "db": str(db_path)}
