# CLAUDE.md: CompuJ take-home (email classifier + dashboard)

Context for Claude Code. `PRD.md` holds the full reasoning and decisions; this file is the working contract for building it. When the two disagree, the PRD wins: flag it and ask.

## What we're building

- `classify.py`: reads each email folder, classifies it with one LLM call per email, writes `classified_emails.json`.
- `build_index.py`: builds a read-only SQLite index (`web/data/emails.db`) from `classified_emails.json` plus the extracted email and PDF text. FTS5 full-text search and faceted filters for analysts. The JSON stays the deliverable and the source of truth; the index is derived and rebuilt from scratch every run.
- Dashboard (`web/`, the brief's "or equivalent" of `index.html` + `style.css` + `app.js`): Svelte 5 single-page app built with Vite, served by a small `Bun.serve` API that queries the index with `bun:sqlite`. List, search, filters, viewer, PDF viewing, news ticker.
- `web/scripts/fetch-news.ts`: refreshes `web/data/news.json` every 10 minutes.
- `README.md`: install and run instructions, plus the decisions on the brief's ambiguities.

The brief is `Hiring Task Instructions .pdf` in the project. Its field list, tag lists and rules are the contract.

## Non-negotiables

- Output records have exactly the brief's ten fields, in this order: `folder_name`, `bank`, `date`, `market_wrap`, `primary_asset_tag`, `asset_tags`, `companies_mentioned`, `industry_subindustry`, `pdf_attachment`, `source_file`. Nothing else. Diagnostics go to `classification_log.jsonl` and `flags.json`.
- Taxonomy constants are copied from the brief word for word. Never edit them to fit an email.
- No dataset-specific rules: no per-bank parsers, no domain-to-bank map, no hard-coded templates. The pipeline must handle emails it hasn't seen.
- Nothing is cut from the LLM input: full email text, full PDF text, all referenced inline images.
- The brief's rules are enforced in code after the LLM (PRD, "Rules applied in code"), not trusted to the prompt.
- Always decode HTML as UTF-8 with bad bytes replaced; declared charsets are unreliable.
- Writing style for docs, README and user-facing text: plain and short, no em dashes, no filler.

## Data

- Location on Caleb's machine: `~/Downloads/Data/` (Arch Linux). Each email is a folder: `emailbody.html`, optional `*.pdf`, `inline/`, and sometimes `thumbs/`.
- Treat every email we've already explored as development data. Evaluation emails are labelled separately and never used to tune prompts or rules.
- Known quirks seen during exploration (handle generally, don't special-case):
  - Declared charsets often don't match the bytes; some files already contain U+FFFD replacement characters.
  - Some bodies start with a mail-security banner or forwarded headers ("From:", "Sent:"). Sent timestamps are not publication dates.
  - Some emails are mostly a pointer to an attached PDF; the PDF carries the content.
  - Occasional non-PDF attachments (e.g. `.xlsx`): flag, don't process.
  - Check how `emailbody.html` references `inline/` images (relative paths, `cid:`, or both) before writing `resolve_images`.

## Stack

- Python 3.11+, managed with `uv` (`pyproject.toml` + `uv.lock`)
- `beautifulsoup4` + `lxml` (HTML), `pypdf` (PDF text), `pydantic` v2 (schemas), `pytest` (tests)
- Date spotting: decide in step 7 between regex-spotting + `python-dateutil` and `dateparser.search`, by which passes the tests with fewer false dates
- LLM provider: Anthropic, `claude-opus-5-5` at effort `medium`, via the `anthropic` SDK (`AnthropicLLMClient` in `pipeline/llm.py`): base64 image input, JSON-schema structured output, server-side refusal fallback. Needs `ANTHROPIC_API_KEY`. Everything goes through the `LLMClient` protocol; tests use a `FakeLLMClient` or a stub SDK, never the network.
- Index: SQLite via Python's `sqlite3` (FTS5). Written by Python so the same text extraction feeds the classifier and the search.
- Web: Bun runtime, Svelte 5 + Vite, TypeScript, `bun:sqlite`, `bun test`. UI logic lives in plain TS modules so it can be unit tested; components stay thin.
- Dashboard design: `docs/design/dashboard-v5-shadcn-compuj.dc.html` ("v5: shadcn x Compu.J", from the Research Dashboard design canvas). Layout of shadcn's Mail example (filters | list | reader), Compu.J skin: near-black panels with thin light borders, Space Grotesk + JetBrains Mono, magenta `#F0287F` with a magenta-to-violet gradient for selection, per-class colours, collapsible filter rail, full-screen reader. Its sample data is placeholder.

## Layout

```
classify.py              # CLI entry point: python classify.py --data ./Data --out classified_emails.json
pipeline/
  taxonomy.py            # brief constants + derived lists
  models.py              # dataclasses and pydantic models from the PRD
  reader.py              # discover_emails, read_folder, flags
  html_text.py           # load_html, html_to_text
  images.py              # resolve_images
  pdfs.py                # extract_pdf_text
  deterministic.py       # title_from_folder_name, find_date_candidates, extract_deterministic
  prompt.py              # build_prompt
  llm.py                 # LLMClient protocol, provider adapter, content-hash cache
  rules.py               # verify_companies, enforce_rules
  run.py                 # run(): orchestration and output writing
  index_db.py            # SQLite index: schema, FTS5, build from JSON + extracted text
build_index.py           # CLI: python build_index.py --json classified_emails.json --data ./Data --out web/data/emails.db
tests/
  fixtures/              # tiny synthetic email folders (+ a few dev emails if needed)
  test_*.py              # one file per module
web/
  server/                # Bun.serve: /api/emails, /api/facets, /api/emails/:id, /raw/:id/...
  src/                   # Svelte app: lib/ (pure TS logic), components/
  scripts/fetch-news.ts  # news.json every 10 minutes
  tests/                 # bun test
README.md
```

## How we work

Build one step at a time, in order. For each step:

1. Write the tests first from the PRD's behaviour.
2. Implement until `uv run pytest` (or `bun test`) passes.
3. Commit each function together with its tests, so every commit is green and small enough to proofread. Conventional Commits (`feat(reader): ...`, `test(...)`, `docs: ...`, `chore: ...`). Commit straight to `main` and push.
4. At the end of the step, show Caleb the commits, diff highlights and test output, explain any decision the PRD didn't settle, then stop for review before the next step.

Prefer small pure functions. No network in unit tests. Keep functions matching the PRD's names and signatures; if a signature needs to change, say why first.

## Build order and what each step's tests must prove

| Step | Module | Tests must prove |
| --- | --- | --- |
| 0 | Scaffold | `pytest` runs; fixtures folder exists; dependencies pinned |
| 1 | `taxonomy.py` | Strings match the brief exactly; `SUB_TO_PARENT` covers every sub-tag; `ALL_INDUSTRY_STRINGS` uses `SECTOR > Subindustry` and includes `Unknown`; 16 checklist entries |
| 2 | `models.py` | `EmailRecord` serialises to exactly the ten fields in brief order; `market_wrap` only `YES`/`NO` |
| 3 | `reader.py` | Missing `emailbody.html` → flagged and skipped; PDFs found in any letter case and sorted; empty or missing `inline/`/`thumbs/` → no flag; anything in `thumbs/`, extra files and extra folders → flagged |
| 4 | `html_text.py` | Scripts/styles removed; text in reading order; a data table keeps header and cell alignment (e.g. Asset / Previous close / Current close / Change with two rows); a layout table with nested tables is flattened, not piped; invalid bytes don't crash |
| 5 | `images.py` | Relative and `cid:` references resolve to `inline/` files; document order kept; each image gets nearby text as context; missing referenced files and unreferenced `inline/` files are flagged; no size filtering |
| 6 | `pdfs.py` | Text extracted from a fixture PDF; a near-empty PDF returns a warning; a broken PDF returns a warning, not a crash |
| 7 | `deterministic.py` | Common date formats found and normalised to YYYY-MM-DD with context; impossible dates rejected; duplicates kept once per context; `title_from_folder_name` returns `None` for an ID like `035239` and the name for a readable subject |
| 8 | `prompt.py` | Prompt contains the taxonomy and checklist verbatim, the materiality definition, the date candidates with context, and image contexts in order |
| 9 | `llm.py` | Fake client satisfies the protocol; cache returns the stored result for identical content and misses on any change; adapter validates responses against `LLMResult` |
| 10 | `rules.py` | One test per rule 1 to 8 in the PRD, plus their order (market wrap YES short-circuits everything) |
| 11 | `run.py` + `classify.py` | End to end on fixtures with the fake client: one record per email folder, valid JSON, exactly ten fields, log and flags written |
| 12 | Live run + evaluation | Real provider on the data; hand-labelled evaluation set (covering every asset class and edge case); per-field scores and run-to-run agreement; reported as an initial evaluation |
| 13a | `index_db.py` + `build_index.py` | Row counts match the JSON; join tables correct; FTS finds a body-only term; rebuild is idempotent; records breaking the ten-field schema are rejected |
| 13b | Bun API (`web/server`) | Each filter alone and combined (OR within a facet, AND across); FTS plus filters; null dates; facet counts; `cid:` rewrite; path traversal rejected; unknown id 404 |
| 13c | Svelte UI | Filter state round-trips through the URL; chips add and remove; query strings built correctly; every brief dashboard requirement met |
| 13d | News ticker | Feed fixture parsed into headlines; `news.json` has `updated_at`; ticker scrolls, pauses on hover, links open the article |
| 13e | README | Install, run order and the ambiguity decisions |

## Open decisions to raise when we reach them

- News source for the ticker (step 13d).
