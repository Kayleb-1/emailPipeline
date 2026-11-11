# Market research email classifier and dashboard

Two parts:

- **`classify.py`** reads each email folder, classifies it with one LLM call, and writes `classified_emails.json` (one entry per email, the brief's ten fields).
- **Dashboard** (`web/`, Svelte 5 on Bun) lets an analyst browse, search, filter and read the emails, with a live news ticker on top.

`PRD.md` explains the design and the reasoning behind it. `CLAUDE.md` is the build contract.

## Requirements

- Python 3.11+ and [uv](https://docs.astral.sh/uv/)
- [Bun](https://bun.sh) 1.4+ (Arch: `sudo pacman -S bun`)
- An Anthropic API key in `ANTHROPIC_API_KEY` (only for classifying)

## Install

```bash
uv sync                  # Python dependencies (pinned in uv.lock)
cd web && bun install    # dashboard dependencies (pinned in bun.lock)
```

## Run

```bash
# 1. Classify the emails (about 200 emails; results are cached in .cache/llm)
uv run python classify.py --data ~/Downloads/Data --out classified_emails.json

# 2. Build the dashboard's search index from the JSON
uv run python build_index.py --json classified_emails.json --data ~/Downloads/Data

# 3. Build and start the dashboard (also refreshes headlines every 10 minutes)
cd web && bun run build && bun run start
# open http://127.0.0.1:3000
```

Useful options:

- `classify.py --model claude-haiku-5-5` for a cheaper run, `--model claude-opus-5-5` for the strongest. Default is `claude-sonnet-5-5`.
- `classify.py --only 035239 035240` to classify a few emails. `--workers 4` sets parallel calls.
- `bun run news` fetches headlines once; `bun run news --watch` keeps refreshing every 10 minutes on its own.
- `bun run dev` runs the API and a Vite dev server with hot reload (http://localhost:5173).

## Outputs

| File | What it holds |
| --- | --- |
| `classified_emails.json` | The deliverable. One record per email folder, exactly the ten fields in the brief's order. |
| `classification_log.jsonl` | Per email: where each value came from, the LLM's raw answer, rules that changed something, extraction warnings, errors. |
| `flags.json` | Files outside the brief's folder definition (anything in `thumbs/`, non-PDF attachments, unreferenced or missing inline images). Not classified, not dropped. |
| `web/data/emails.db` | SQLite search index, rebuilt from the JSON. Never edited. |
| `web/data/news.json` | Latest headlines for the ticker. |

## How classification works

1. **Read** each folder: `emailbody.html` (required), every PDF, and the `inline/` images the HTML references.
2. **Extract** text: HTML always decoded as UTF-8; data tables kept as aligned rows, layout tables flattened; full PDF text; images in document order with their nearby text.
3. **Fill what is certain** in code: `source_file`, `pdf_attachment`, the folder name when it reads as a subject, and every date in the text with its context.
4. **One LLM call** per email with the full text, PDF text and images. The output is constrained to the brief's tag and industry lists.
5. **Apply the brief's rules in code**, so every record follows them whatever the model returned: market wrap fields, tags in the list only, sub-tags bring their parent, primary tag in the tags, companies and industries for Equity only, `Unknown` industry when none fits, companies must appear in the text, date must be one of the dates found in the email.

Nothing is cut from the model's input and nothing is tied to a particular bank or template.

## Decisions on the brief's open points

| Question | Decision |
| --- | --- |
| `folder_name` when the folder is an ID | Every folder in the data is an ID (e.g. `035239`), so the title comes from the email content. A readable folder name would be used as is. |
| `pdf_attachment` shape | Always a list of filenames when there are PDFs, otherwise `null`. |
| No publication date | `null`. The model picks the publication date from dates found in the email, never invents one. |
| Several dates in one email | The model chooses using each date's context, so event dates, deadlines and sent timestamps aren't mistaken for the publication date. |
| Market wrap | Judged against the brief's definition and checklist as a whole, not by requiring every answer to be yes. |
| `Thematics` vs `Equity > Thematic Investing` | `Thematics` when there's no equity angle; `Equity` + `Thematic Investing` when the theme is expressed through stocks or sectors. |
| "Materially discussed" companies | The email says something about the company itself (business, results, estimates, valuation, rating, outlook). Peers named for comparison, examples, names in lists, tables, sources or disclaimers, and the publishing bank don't count. |
| Digest emails | Tag everything materially covered; the dominant topic is primary. |
| Duplicate emails | One record per folder, so duplicates are classified separately. |
| Unexpected files | Flagged in `flags.json` for another pass. |
| Temperature | The current API doesn't accept sampling parameters. Stability comes from a fixed prompt, constrained output and the cache. |

## Dashboard

- Scrollable list with title, bank, date, PDF marker and asset tags; Newest/Oldest sort.
- Search across title, bank, companies, industries and the full email and PDF text, with highlighted matches.
- Multi-select filters for asset class (expandable to sub-tags), bank and month, each with counts. Active filters show as removable chips. OR within a filter, AND across filters.
- Reader with the email in a sandboxed iframe (no scripts; remote images off until you ask, since they can report the open to the sender), PDF tabs in the browser's viewer, an Equity panel (companies, industries), and full screen.
- News ticker from CNBC, MarketWatch, Yahoo Finance and FT Markets RSS feeds. It scrolls, pauses on hover, shows when it was last updated, and opens articles in a new tab.
- The view lives in the URL, so a filtered view or a selected note can be bookmarked or shared.

### Why SQLite

The JSON is the deliverable and the source of truth. The index is derived from it so analysts can search inside the emails and PDFs, not just the tags, and filter with live counts. At this size the browser could filter the JSON alone; the index is for retrieval, not speed.

## Tests

```bash
uv run pytest                       # pipeline
cd web && bun test && bun run check # API, UI logic, news; Svelte type check
```

No test touches the network or the LLM: they use small synthetic email folders, a fake LLM client and saved feed fixtures.

## Layout

```
classify.py, build_index.py   CLIs
pipeline/                     reader, html_text, images, pdfs, deterministic, prompt, llm, rules, run, index_db
tests/                        pytest, one file per module
web/server/                   Bun API (queries, safe file serving)
web/src/                      Svelte app (lib/ logic, components/)
web/scripts/fetch-news.ts     headline fetcher
docs/design/                  dashboard design reference
```
