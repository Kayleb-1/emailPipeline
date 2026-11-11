"""Pick an evaluation set by coverage and write a blank labelling template.

    uv run python -m eval.make_template --pred classified_emails.json --log classification_log.jsonl

Coverage over randomness (PRD, section 4): every primary asset class, market
wraps, Equity notes with companies, emails with PDFs, with images, and without
a date. The template's fields are blank on purpose, so labels are made against
the brief, not anchored on the model's answers. Fill in eval/labels.json, then
run eval.score.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

from eval.score import load
from pipeline.models import BRIEF_FIELD_ORDER

BUCKETS = ("Macro", "Fixed Income", "Equity", "Commodities", "FX", "Thematics", "Market Wrap")


def pick(pred: dict[str, dict], log: dict[str, dict], size: int = 20, seed: int = 7) -> list[str]:
    rng = random.Random(seed)
    ids = sorted(pred)
    chosen: list[str] = []

    def take(cands: list[str], n: int) -> None:
        cands = [c for c in cands if c not in chosen]
        rng.shuffle(cands)
        chosen.extend(cands[:n])

    for tag in BUCKETS:
        take([i for i in ids if pred[i]["primary_asset_tag"] == tag], 2)
    take([i for i in ids if pred[i]["companies_mentioned"]], 2)
    take([i for i in ids if pred[i]["pdf_attachment"]], 2)
    take([i for i in ids if log.get(i, {}).get("images")], 2)
    take([i for i in ids if pred[i]["date"] is None], 2)
    take(ids, max(0, size - len(chosen)))
    return sorted(chosen)  # coverage first, so this can exceed size


def template(ids: list[str]) -> list[dict]:
    blank = {f: None for f in BRIEF_FIELD_ORDER}
    return [{**blank, "source_file": i, "market_wrap": "", "asset_tags": [],
             "companies_mentioned": [], "industry_subindustry": []} for i in ids]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--pred", type=Path, default=Path("classified_emails.json"))
    p.add_argument("--log", type=Path, default=Path("classification_log.jsonl"))
    p.add_argument("--out", type=Path, default=Path("eval/labels_template.json"))
    p.add_argument("--size", type=int, default=20, help="minimum; coverage can add more")
    args = p.parse_args(argv)
    log = {}
    if args.log.exists():
        for line in args.log.read_text(encoding="utf-8").splitlines():
            entry = json.loads(line)
            log[entry["source_file"]] = entry
    ids = pick(load(args.pred), log, args.size)
    args.out.write_text(json.dumps(template(ids), indent=2) + "\n", encoding="utf-8")
    print(f"{len(ids)} emails -> {args.out}: {' '.join(ids)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
