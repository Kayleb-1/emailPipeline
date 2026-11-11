"""Score predictions against hand labels, and compare two runs.

    uv run python -m eval.score --pred classified_emails.json --labels eval/labels.json
    uv run python -m eval.score --pred run1.json --compare run2.json

Labels use the same ten-field records as the output, for a subset of emails.
Scores (PRD, "Scores per field"):
- folder_name, bank, date, primary_asset_tag: exact match (titles and banks
  compared case- and whitespace-insensitively)
- market_wrap: confusion matrix
- asset_tags, companies_mentioned, industry_subindustry: micro precision, recall, F1
With a set this small, results are an initial evaluation: they show where the
pipeline fails, not representative accuracy.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

EXACT = ("folder_name", "bank", "date", "primary_asset_tag")
SETS = ("asset_tags", "companies_mentioned", "industry_subindustry")
LOOSE = {"folder_name", "bank", "companies_mentioned"}


def _norm(field: str, value):
    if value is None:
        return None
    if field in LOOSE and isinstance(value, str):
        return re.sub(r"\s+", " ", value).strip().casefold()
    return value


def _as_set(field: str, values) -> set:
    return {_norm(field, v) for v in (values or [])}


def load(path: Path) -> dict[str, dict]:
    records = json.loads(path.read_text(encoding="utf-8"))
    return {r["source_file"]: r for r in records}


def prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if tp + fp else 1.0
    r = tp / (tp + fn) if tp + fn else 1.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {"precision": round(p, 3), "recall": round(r, 3), "f1": round(f, 3), "tp": tp, "fp": fp, "fn": fn}


def score(pred: dict[str, dict], labels: dict[str, dict]) -> dict:
    ids = sorted(labels)
    missing = [i for i in ids if i not in pred]
    scored = [i for i in ids if i in pred]
    out: dict = {"labelled": len(ids), "scored": len(scored), "missing_predictions": missing, "fields": {}}

    for field in EXACT:
        hits = [i for i in scored if _norm(field, pred[i][field]) == _norm(field, labels[i][field])]
        out["fields"][field] = {
            "accuracy": round(len(hits) / len(scored), 3) if scored else None,
            "wrong": [{"source_file": i, "pred": pred[i][field], "label": labels[i][field]}
                      for i in scored if i not in hits],
        }

    matrix = Counter((labels[i]["market_wrap"], pred[i]["market_wrap"]) for i in scored)
    out["fields"]["market_wrap"] = {
        "confusion": {f"label_{l}_pred_{p}": matrix[(l, p)] for l in ("YES", "NO") for p in ("YES", "NO")},
        "accuracy": round((matrix[("YES", "YES")] + matrix[("NO", "NO")]) / len(scored), 3) if scored else None,
    }

    for field in SETS:
        tp = fp = fn = 0
        per_tag: dict[str, Counter] = {}
        for i in scored:
            p, g = _as_set(field, pred[i][field]), _as_set(field, labels[i][field])
            tp, fp, fn = tp + len(p & g), fp + len(p - g), fn + len(g - p)
            if field == "asset_tags":
                for t in p | g:
                    c = per_tag.setdefault(t, Counter())
                    c["tp" if t in p and t in g else "fp" if t in p else "fn"] += 1
        out["fields"][field] = prf(tp, fp, fn)
        if per_tag:
            out["fields"][field]["per_tag"] = {t: prf(c["tp"], c["fp"], c["fn"]) for t, c in sorted(per_tag.items())}
    return out


def agreement(a: dict[str, dict], b: dict[str, dict]) -> dict:
    """Share of emails where two runs gave the same value, per field."""
    ids = sorted(set(a) & set(b))
    fields = EXACT + ("market_wrap",) + SETS
    out = {}
    for field in fields:
        same = sum(
            1 for i in ids
            if (_as_set(field, a[i][field]) == _as_set(field, b[i][field]) if field in SETS
                else _norm(field, a[i][field]) == _norm(field, b[i][field]))
        )
        out[field] = round(same / len(ids), 3) if ids else None
    return {"compared": len(ids), "agreement": out}


def distribution(pred: dict[str, dict]) -> dict:
    recs = list(pred.values())
    n = len(recs) or 1
    return {
        "records": len(recs),
        "null_date_rate": round(sum(r["date"] is None for r in recs) / n, 3),
        "market_wrap_rate": round(sum(r["market_wrap"] == "YES" for r in recs) / n, 3),
        "primary_tags": dict(Counter(r["primary_asset_tag"] for r in recs).most_common()),
        "banks": dict(Counter(r["bank"] for r in recs).most_common()),
        "unknown_industry": sum(r["industry_subindustry"] == ["Unknown"] for r in recs),
        "equity_without_companies": sum("Equity" in r["asset_tags"] and not r["companies_mentioned"] for r in recs),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Score classified emails")
    p.add_argument("--pred", type=Path, required=True)
    p.add_argument("--labels", type=Path)
    p.add_argument("--compare", type=Path, help="a second run, for run-to-run agreement")
    p.add_argument("--out", type=Path, help="write the full report as JSON")
    args = p.parse_args(argv)

    pred = load(args.pred)
    report: dict = {"distribution": distribution(pred)}
    if args.labels:
        report["scores"] = score(pred, load(args.labels))
    if args.compare:
        report["run_to_run"] = agreement(pred, load(args.compare))
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
