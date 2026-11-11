"""Consistency across the run: one spelling per bank.

The model names the publishing bank per email, so the same bank can come back
as "J.P. Morgan" and "JPMorgan", or "UBP" and "Union Bancaire Privée". That
splits the dashboard's bank filter. This groups names that differ only in
case, accents, punctuation, legal suffixes or generic words ("Bank", "Asset
Management"), or where one is the acronym of the other, and uses the most
frequent spelling for the group. No list of banks is involved.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter

from pipeline.models import EmailRecord

_GENERIC = {
    "bank", "banque", "group", "groupe", "holding", "holdings", "asset", "management",
    "wealth", "private", "securities", "research", "global", "investment", "investments",
    "ag", "sa", "plc", "inc", "llc", "ltd", "limited", "nv", "se", "co", "corp", "the", "and", "of",
}


def _words(name: str) -> list[str]:
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().casefold()
    return re.findall(r"[a-z0-9]+", plain.replace("&", " and "))


def bank_key(name: str) -> str:
    """Words without generic ones, joined without spaces ("J.P. Morgan" -> "jpmorgan")."""
    words = _words(name)
    core = [w for w in words if w not in _GENERIC] or words
    return "".join(core)


def _acronym(name: str) -> str:
    words = [w for w in _words(name) if w not in {"the", "and", "of", "de", "du", "la"}]
    return "".join(w[0] for w in words) if len(words) >= 2 else ""


def canonical_banks(names: list[str]) -> dict[str, str]:
    """Map every name to the most frequent spelling in its group."""
    counts = Counter(names)
    unique = sorted(counts)
    parent = {n: n for n in unique}

    def find(n: str) -> str:
        while parent[n] != n:
            parent[n] = parent[parent[n]]
            n = parent[n]
        return n

    def union(a: str, b: str) -> None:
        parent[find(a)] = find(b)

    by_key: dict[str, str] = {}
    for n in unique:
        k = bank_key(n)
        if k in by_key:
            union(n, by_key[k])
        else:
            by_key[k] = n
    for short in unique:
        key = bank_key(short)
        if len(key) < 2:
            continue
        for long in unique:
            if long != short and _acronym(long) == key:
                union(short, long)

    groups: dict[str, list[str]] = {}
    for n in unique:
        groups.setdefault(find(n), []).append(n)
    mapping: dict[str, str] = {}
    for members in groups.values():
        best = max(members, key=lambda m: (counts[m], len(m), m))
        for m in members:
            mapping[m] = best
    return mapping


def harmonise_banks(records: list[EmailRecord]) -> tuple[list[EmailRecord], dict[str, str]]:
    """Records with one spelling per bank, and the renames applied."""
    mapping = canonical_banks([r.bank for r in records])
    changed = {old: new for old, new in mapping.items() if old != new}
    out = [r.model_copy(update={"bank": mapping[r.bank]}) if r.bank in changed else r for r in records]
    return out, changed
