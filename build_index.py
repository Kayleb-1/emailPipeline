"""Build the dashboard's SQLite index from classified_emails.json.

    uv run python build_index.py --json classified_emails.json --data ~/Downloads/Data

The index is derived and rebuilt from scratch each time; the JSON is the source of truth.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pipeline.index_db import IndexBuildError, build_index


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--json", type=Path, default=Path("classified_emails.json"))
    p.add_argument("--data", type=Path, default=Path("Data"))
    p.add_argument("--out", type=Path, default=Path("web/data/emails.db"))
    args = p.parse_args(argv)
    try:
        summary = build_index(args.json, args.data.expanduser(), args.out)
    except (IndexBuildError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    for w in summary["warnings"]:
        print(f"warning: {w}", file=sys.stderr)
    print(f"indexed {summary['records']} emails into {summary['db']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
