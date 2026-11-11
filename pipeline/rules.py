"""The brief's rules, applied in code after the LLM so every record follows them.

Order (PRD, "Rules applied in code"):
1. Market wrap YES: fixed wrap fields, companies and industries empty. Stop.
2. Drop any tag not in the brief's list.
3. A sub-tag brings in its parent.
4. primary_asset_tag must be a primary class and must be in asset_tags.
5. No Equity: companies and industries empty.
6. Equity: drop industry strings not in the brief's list; none left -> ["Unknown"].
7. Drop companies whose name doesn't appear in the email or PDF text.
8. date must be one of the extracted candidates, otherwise null.

Every change a rule makes is described in ``notes`` for the classification log.
"""

from __future__ import annotations

import re
import unicodedata

from pipeline import taxonomy as tx
from pipeline.models import DeterministicFields, EmailRecord, LLMResult


class RulesError(ValueError):
    """The LLM result can't be made into a valid record (no usable asset class)."""


# Legal-form suffixes a model may add or drop ("Siemens" vs "Siemens AG").
_LEGAL_SUFFIX = re.compile(
    r"[\s,]+(inc|incorporated|corp|corporation|co|company|ltd|limited|plc|llc|lp|ag|se|sa|"
    r"spa|s\.p\.a|nv|n\.v|bv|ab|asa|oyj|as|a/s|kgaa|holdings?|group)\.?$",
    re.I,
)


def _normalise(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    text = text.replace("’", "'").replace("‘", "'").replace("&amp;", "&")
    return re.sub(r"\s+", " ", text).strip()


def _appears(name: str, corpus: str) -> bool:
    if not name:
        return False
    pattern = r"(?<!\w)" + re.escape(name) + r"(?!\w)"
    return re.search(pattern, corpus) is not None


def verify_companies(names: list[str], corpus: str) -> list[str]:
    """Keep names found in the text (case and spacing ignored, legal suffix optional)."""
    text = _normalise(corpus)
    kept: list[str] = []
    seen: set[str] = set()
    for raw in names:
        name = raw.strip()
        norm = _normalise(name)
        if not norm or norm in seen:
            continue
        base = _LEGAL_SUFFIX.sub("", norm).strip()
        if _appears(norm, text) or (len(base) >= 2 and _appears(base, text)):
            kept.append(name)
            seen.add(norm)
    return kept


def _ordered_tags(tags: set[str]) -> list[str]:
    """Brief order: each primary class followed by its sub-tags."""
    out: list[str] = []
    for primary, subs in tx.ASSET_TAXONOMY.items():
        if primary in tags:
            out.append(primary)
        out.extend(s for s in subs if s in tags)
    return out


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    return [x for x in items if not (x in seen or seen.add(x))]


def enforce_rules(
    det: DeterministicFields,
    llm: LLMResult,
    corpus: str,
    notes: list[str] | None = None,
) -> EmailRecord:
    notes = notes if notes is not None else []

    title = det.folder_name or llm.title.strip() or det.source_file
    bank = llm.bank.strip() or "Unknown"

    # Rule 8 is independent of the tags, so settle the date first.
    candidates = {c.iso for c in det.date_candidates}
    date = llm.date_choice if llm.date_choice in candidates else None
    if llm.date_choice and date is None:
        notes.append(f"rule 8: date {llm.date_choice!r} is not an extracted candidate, set null")

    common = dict(
        folder_name=title, bank=bank, date=date,
        pdf_attachment=det.pdf_attachment, source_file=det.source_file,
    )

    # Market wrap as the model judged it; a wrap primary with nothing else valid
    # is also a wrap (the tags agree with each other, the boolean was the slip).
    valid = [t for t in llm.asset_tags if t in tx.ALL_ASSET_TAGS]
    non_wrap = [t for t in valid if t != tx.MARKET_WRAP]
    is_wrap = llm.market_wrap or (
        llm.primary_asset_tag == tx.MARKET_WRAP and not non_wrap
    )
    if is_wrap and not llm.market_wrap:
        notes.append("rule 1: primary tag was Market Wrap with no other tags, treated as YES")

    # Rule 1
    if is_wrap:
        if (llm.primary_asset_tag != tx.MARKET_WRAP or llm.asset_tags != [tx.MARKET_WRAP]
                or llm.companies_mentioned or llm.industry_subindustry):
            notes.append("rule 1: market wrap YES, set wrap tags and cleared companies/industries")
        return EmailRecord(
            market_wrap="YES", primary_asset_tag=tx.MARKET_WRAP, asset_tags=[tx.MARKET_WRAP],
            companies_mentioned=[], industry_subindustry=[], **common,
        )

    # Rule 2
    dropped = [t for t in llm.asset_tags if t not in tx.ALL_ASSET_TAGS]
    if dropped:
        notes.append(f"rule 2: dropped unknown tags {dropped}")
    if tx.MARKET_WRAP in valid:
        notes.append("rule 2: dropped Market Wrap tag because market_wrap is NO")
    tags = set(non_wrap)

    # Rule 3
    for tag in list(tags):
        parent = tx.SUB_TO_PARENT.get(tag)
        if parent and parent not in tags:
            tags.add(parent)
            notes.append(f"rule 3: added parent {parent!r} for sub-tag {tag!r}")

    # Rule 4
    primary = llm.primary_asset_tag
    if primary in tx.SUB_TO_PARENT:
        notes.append(f"rule 4: primary {primary!r} is a sub-tag, using its parent")
        primary = tx.SUB_TO_PARENT[primary]
        tags.add(primary)
    if primary not in tx.PRIMARY_ASSET_TAGS or primary == tx.MARKET_WRAP:
        candidates_p = [t for t in _ordered_tags(tags) if t in tx.PRIMARY_ASSET_TAGS]
        if not candidates_p:
            raise RulesError(
                f"no usable asset class: primary {llm.primary_asset_tag!r}, tags {llm.asset_tags}"
            )
        notes.append(f"rule 4: primary {llm.primary_asset_tag!r} invalid, using {candidates_p[0]!r}")
        primary = candidates_p[0]
    if primary not in tags:
        tags.add(primary)
        notes.append(f"rule 4: added primary {primary!r} to asset_tags")
    asset_tags = _ordered_tags(tags)

    # Rule 5
    if tx.EQUITY not in tags:
        if llm.companies_mentioned or llm.industry_subindustry:
            notes.append("rule 5: no Equity tag, cleared companies and industries")
        return EmailRecord(
            market_wrap="NO", primary_asset_tag=primary, asset_tags=asset_tags,
            companies_mentioned=[], industry_subindustry=[], **common,
        )

    # Rule 6
    industries = _unique([s for s in llm.industry_subindustry if s in tx.ALL_INDUSTRY_STRINGS])
    bad = [s for s in llm.industry_subindustry if s not in tx.ALL_INDUSTRY_STRINGS]
    if bad:
        notes.append(f"rule 6: dropped unknown industries {bad}")
    if len(industries) > 1 and tx.UNKNOWN_INDUSTRY in industries:
        industries.remove(tx.UNKNOWN_INDUSTRY)
        notes.append("rule 6: dropped Unknown next to known industries")
    if not industries:
        industries = [tx.UNKNOWN_INDUSTRY]
        if llm.industry_subindustry != [tx.UNKNOWN_INDUSTRY]:
            notes.append("rule 6: no valid industry left, set ['Unknown']")

    # Rule 7
    companies = verify_companies(llm.companies_mentioned, corpus)
    kept_norm = {_normalise(c) for c in companies}
    missing = [c for c in llm.companies_mentioned if _normalise(c) not in kept_norm]
    if missing:
        notes.append(f"rule 7: dropped companies not found in the text {missing}")

    return EmailRecord(
        market_wrap="NO", primary_asset_tag=primary, asset_tags=asset_tags,
        companies_mentioned=companies, industry_subindustry=industries, **common,
    )
