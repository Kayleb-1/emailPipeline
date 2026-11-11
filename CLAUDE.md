# CLAUDE.md: CompuJ take-home (email classifier + dashboard)

Context for Claude Code. `PRD.md` holds the full reasoning and decisions; this file is the working contract for building it. When the two disagree, the PRD wins: flag it and ask.

## What we're building

- `classify.py`: reads each email folder, classifies it with one LLM call per email, writes `classified_emails.json`.
- Dashboard (`index.html`, `style.css`, `app.js`): reads that JSON; list, search, filters, viewer, PDF viewing, news ticker.
- `fetch_news.py`: refreshes `news.json` every 10 minutes.
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

- Python 3.11+
- `beautifulsoup4` + `lxml` (HTML), `pypdf` (PDF text), `pydantic` v2 (schemas), `pytest` (tests)
- Date spotting: decide in step 7 between regex-spotting + `python-dateutil` and `dateparser.search`, by which passes the tests with fewer false dates
- LLM provider: **not chosen yet**. Must support image input and structured output. Everything goes through the `LLMClient` protocol; tests use a `FakeLLMClient`, never the network.

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
tests/
  fixtures/              # tiny synthetic email folders (+ a few dev emails if needed)
  test_*.py              # one file per module
fetch_news.py
index.html  style.css  app.js
README.md
```

## How we work

Build one step at a time, in order. For each step:

1. Write the tests first from the PRD's behaviour.
2. Implement until `pytest` passes.
3. Show Caleb the diff and test output, explain any decision the PRD didn't settle, then stop for review before the next step.
4. Commit only when asked.

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
| 13 | Dashboard, `fetch_news.py`, README | Every brief requirement for the dashboard and ticker met; README covers install, run and the ambiguity decisions |

## Open decisions to raise when we reach them

- LLM provider (before step 9).
- Date-spotting library (step 7).
- Exact boundary between data tables and layout tables (step 4), decided with fixtures.
- News source for the ticker (step 13).
