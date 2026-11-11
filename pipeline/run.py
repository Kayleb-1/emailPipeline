"""Orchestration: read every email folder, classify it, write the outputs.

Outputs:
- classified_emails.json: one record per email folder with HTML, the ten fields only.
- classification_log.jsonl: per email, where each value came from, rules that
  changed something, extraction warnings, errors.
- flags.json: files the reader and image resolver flagged for another pass.

One failing email is logged and skipped; the rest still get written.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path

from pipeline.deterministic import extract_deterministic
from pipeline.html_text import html_to_text, load_html
from pipeline.images import resolve_images
from pipeline.llm import CachedLLMClient, LLMClient, classify_email
from pipeline.models import EmailFolder, EmailRecord, Flag, ParsedEmail
from pipeline.pdfs import extract_pdf_text
from pipeline.reader import email_dirs, read_folder
from pipeline.rules import enforce_rules

log = logging.getLogger("classify")


def parse_email(folder: EmailFolder) -> tuple[ParsedEmail, list[Flag]]:
    html = load_html(folder.html_path)
    images, flags = resolve_images(html, folder)
    pdf_texts: dict[str, str] = {}
    warnings: list[str] = []
    for path in folder.pdf_paths:
        text, warning = extract_pdf_text(path)
        pdf_texts[path.name] = text
        if warning:
            warnings.append(warning)
    parsed = ParsedEmail(
        folder=folder, text=html_to_text(html), pdf_texts=pdf_texts,
        pdf_warnings=warnings, images=images,
    )
    return parsed, flags


def corpus_of(parsed: ParsedEmail) -> str:
    return "\n\n".join([parsed.text, *parsed.pdf_texts.values()])


def _classify_one(folder: EmailFolder, client: LLMClient) -> tuple[EmailRecord | None, dict, list[Flag]]:
    entry: dict = {"source_file": folder.source_file}
    parsed, flags = parse_email(folder)
    det = extract_deterministic(parsed)
    entry.update(
        text_chars=len(parsed.text),
        pdfs={name: len(text) for name, text in parsed.pdf_texts.items()},
        pdf_warnings=parsed.pdf_warnings,
        images=[img.path.name for img in parsed.images],
        date_candidates=[asdict(c) for c in det.date_candidates],
    )
    try:
        result = classify_email(parsed, det, client)
    except Exception as exc:  # provider, network or schema failure: log, keep going
        entry.update(status="error", error=f"{type(exc).__name__}: {exc}")
        return None, entry, flags
    inner = getattr(client, "inner", client)
    if getattr(inner, "last_warnings", None):
        entry["image_warnings"] = list(inner.last_warnings)

    notes: list[str] = []
    try:
        record = enforce_rules(det, result, corpus_of(parsed), notes)
    except ValueError as exc:
        entry.update(status="error", error=f"{type(exc).__name__}: {exc}",
                     llm=result.model_dump(), rules=notes)
        return None, entry, flags
    entry.update(
        status="ok",
        sources={
            "folder_name": "folder" if det.folder_name else "llm",
            "bank": "llm",
            "date": "llm choice from candidates" if record.date else "null",
            "pdf_attachment": "folder",
            "source_file": "folder",
        },
        llm=result.model_dump(),
        rules=notes,
    )
    return record, entry, flags


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def run(
    data_dir: Path,
    out_path: Path,
    client: LLMClient | None = None,
    *,
    log_path: Path | None = None,
    flags_path: Path | None = None,
    cache_dir: Path | None = None,
    workers: int = 4,
    only: list[str] | None = None,
) -> dict:
    """Classify every email folder under ``data_dir``. Returns a summary dict."""
    if client is None:
        from pipeline.llm import make_client

        client = make_client()
    if cache_dir is not None:
        client = CachedLLMClient(client, cache_dir)
    log_path = log_path or out_path.with_name("classification_log.jsonl")
    flags_path = flags_path or out_path.with_name("flags.json")

    folders: list[EmailFolder] = []
    flags: list[Flag] = []
    entries: list[dict] = []
    for d in email_dirs(data_dir):
        if only and d.name not in only:
            continue
        folder, folder_flags = read_folder(d)
        flags.extend(folder_flags)
        if folder.html_path is None:
            entries.append({"source_file": folder.source_file, "status": "skipped",
                            "error": "no emailbody.html"})
            continue
        folders.append(folder)

    def work(folder: EmailFolder):
        log.info("classifying %s", folder.source_file)
        try:
            return _classify_one(folder, client)
        except Exception as exc:  # extraction bug: keep the run alive, log it
            return None, {"source_file": folder.source_file, "status": "error",
                          "error": f"{type(exc).__name__}: {exc}"}, []

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        results = list(pool.map(work, folders))

    records: list[EmailRecord] = []
    for record, entry, image_flags in results:
        flags.extend(image_flags)
        entries.append(entry)
        if record is not None:
            records.append(record)

    records.sort(key=lambda r: r.source_file)
    entries.sort(key=lambda e: e["source_file"])
    flags.sort(key=lambda f: (f.source_file, f.path))

    _write_json(out_path, [r.to_json_dict() for r in records])
    _write_json(flags_path, [asdict(f) for f in flags])
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    summary = {
        "folders": len(folders) + sum(1 for e in entries if e["status"] == "skipped"),
        "records": len(records),
        "errors": sum(1 for e in entries if e["status"] == "error"),
        "skipped": sum(1 for e in entries if e["status"] == "skipped"),
        "flags": len(flags),
    }
    if isinstance(client, CachedLLMClient):
        summary.update(cache_hits=client.hits, cache_misses=client.misses)
    return summary
