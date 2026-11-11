"""Classify market research emails into classified_emails.json.

    uv run python classify.py --data ~/Downloads/Data --out classified_emails.json

The model is pluggable (--provider). The default, claude-code, runs Claude through
the local Claude Code CLI on your own login, so no API key is needed; anthropic
uses the API with ANTHROPIC_API_KEY. Answers are saved in llm_cache/ (committed), so
re-runs only call the model for emails whose content (or the prompt) changed.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from pipeline.llm import DEFAULT_EFFORT, DEFAULT_PROVIDER, PROVIDERS, LLMClient, make_client
from pipeline.run import run


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--data", type=Path, default=Path("Data"), help="folder of email folders")
    p.add_argument("--out", type=Path, default=Path("classified_emails.json"))
    p.add_argument("--log", type=Path, default=None, help="default: next to --out")
    p.add_argument("--flags", type=Path, default=None, help="default: next to --out")
    p.add_argument("--cache", type=Path, default=Path("llm_cache"),
                   help="saved model answers, keyed by a hash of the exact input")
    p.add_argument("--no-cache", action="store_true")
    p.add_argument("--workers", type=int, default=3, help="parallel LLM calls")
    p.add_argument("--provider", default=DEFAULT_PROVIDER, choices=sorted(PROVIDERS),
                   help="; ".join(f"{k}: {v['note']}" for k, v in PROVIDERS.items()))
    p.add_argument("--model", default=None,
                   help="model for the provider (default: " + ", ".join(
                       f"{k}={v['default_model']}" for k, v in PROVIDERS.items()) + ")")
    p.add_argument("--effort", default=DEFAULT_EFFORT,
                   choices=["low", "medium", "high", "xhigh", "max"], help="anthropic provider only")
    p.add_argument("--only", nargs="*", help="classify only these folder names")
    return p.parse_args(argv)


def main(argv: list[str] | None = None, client: LLMClient | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    if not args.data.is_dir():
        print(f"data folder not found: {args.data}", file=sys.stderr)
        return 2
    if client is None:
        client = make_client(args.provider, args.model, args.effort)
    summary = run(
        args.data.expanduser(), args.out, client,
        log_path=args.log, flags_path=args.flags,
        cache_dir=None if args.no_cache else args.cache,
        workers=args.workers, only=args.only,
    )
    print(" ".join(f"{k}={v}" for k, v in summary.items()))
    return 1 if summary["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
