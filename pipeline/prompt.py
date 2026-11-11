"""The classification prompt: brief's taxonomy, definitions and checklist, then the email.

System prompt: the task, the brief's lists and rules verbatim, our definitions
for the brief's open questions (PRD, "Open questions and ambiguities").
User prompt: date candidates, the full email text, every PDF's full text and
the list of attached images with their nearby text. Nothing is cut.
"""

from __future__ import annotations

from pipeline import taxonomy as tx
from pipeline.models import DeterministicFields, ParsedEmail

# PRD, "Companies: what counts as material", used verbatim.
MATERIALITY_DEFINITION = (
    "A company is material when the email says something about the company itself "
    "(its business, results, estimates, valuation, rating or outlook). Not material: "
    "peers named only for comparison, companies cited as an example, names in lists, "
    "tables, charts, source lines or disclaimers, and the publishing bank."
)


def _asset_table() -> str:
    return "\n".join(
        f"- {primary}: {', '.join(subs) if subs else 'No sub-tags'}"
        for primary, subs in tx.ASSET_TAXONOMY.items()
    )


def _industry_list() -> str:
    return "\n".join(f"- {s}" for s in tx.ALL_INDUSTRY_STRINGS)


def _checklist() -> str:
    return "\n".join(f"- {q}" for q in tx.MARKET_WRAP_CHECKLIST.values())


def system_prompt() -> str:
    return f"""You classify market research emails from investment banks for a research dashboard.
Read the whole email: its text, every attached PDF's text and every attached image. Evidence can be anywhere, including sender lines, links, disclaimers and attachments.

## Step 1: Market Wrap
Decide first whether the email is a Market Wrap. {tx.MARKET_WRAP_DEFINITION}.
Judge it against this checklist as a whole. It describes a judgement, not a rule that every answer must be yes:
{_checklist()}
If it is a Market Wrap, set market_wrap true, primary_asset_tag "{tx.MARKET_WRAP}", asset_tags ["{tx.MARKET_WRAP}"], and leave companies_mentioned and industry_subindustry empty.

## Step 2: Asset tags (when not a Market Wrap)
Use ONLY these tags. Primary asset classes and their sub-tags:
{_asset_table()}
Important tagging rules:
{chr(10).join(f"- {r}" for r in tx.ASSET_TAGGING_RULES)}
- asset_tags lists ALL materially covered tags, primary classes and sub-tags. A sub-tag always comes with its primary class.
- primary_asset_tag is the single most important primary class, and must be one of the primary classes above.
- Use "Thematics" for thematic research without an equity angle; use "Equity" with "Thematic Investing" when the theme is expressed through stocks or sectors.
- If the email bundles several notes, tag everything materially covered and make the dominant topic primary.

## Step 3: Companies (Equity only)
Only when "{tx.EQUITY}" is in asset_tags; otherwise leave companies_mentioned empty.
List only material companies. {MATERIALITY_DEFINITION}
Write each company name exactly as it appears in the email or PDF text.

## Step 4: Industries (Equity only)
{tx.INDUSTRY_TAGGING_RULE}
Format: SECTOR > Subindustry. Use ONLY these strings:
{_industry_list()}
{tx.UNKNOWN_INDUSTRY_RULE}

## Other fields
- title: the subject or title of the research note as the email presents it (its heading or subject line). Do not invent one.
- bank: the investment bank that published the research, by its common name without legal suffixes or branch names (PLC, AG, SA, Inc., London Branch). Not a distributor or forwarder.
- date_choice: the publication date, chosen from the numbered date candidates by its YYYY-MM-DD value. Use the context to tell a publication date from event dates, deadlines, data as-of dates and sent or forwarded timestamps. If no candidate is clearly the publication date, use null.
"""


def user_prompt(parsed: ParsedEmail, det: DeterministicFields) -> str:
    parts: list[str] = []
    if det.folder_name:
        parts.append(f"Folder name (subject): {det.folder_name}")

    if det.date_candidates:
        lines = [f"{i}. {c.iso}: {c.context}" for i, c in enumerate(det.date_candidates, 1)]
        parts.append("## Date candidates\n" + "\n".join(lines))
    else:
        parts.append("## Date candidates\nNone found. date_choice must be null.")

    parts.append("## Email text\n" + (parsed.text or "(empty)"))

    for name, text in parsed.pdf_texts.items():
        parts.append(f"## Attached PDF: {name}\n" + (text or "(no extractable text)"))

    if parsed.images:
        lines = [
            f"Image {i} ({img.path.name}): {img.context or 'no nearby text'}"
            for i, img in enumerate(parsed.images, 1)
        ]
        parts.append(
            "## Attached images, in the order they appear in the email\n" + "\n".join(lines)
        )
    return "\n\n".join(parts)


def build_prompt(parsed: ParsedEmail, det: DeterministicFields) -> tuple[str, str]:
    return system_prompt(), user_prompt(parsed, det)
