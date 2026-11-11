"""Fields code can fill with certainty, and date candidates for the LLM.

Dates: every full date (day, month and year) in the email and PDF text is
collected with the text around it, normalised to YYYY-MM-DD. The LLM picks the
publication date from these, since a lone date can still be an event, a
deadline or a sent timestamp. Regex spotting with stdlib validation was chosen
over ``dateparser.search``, which reads common words ("may", "now") as dates.
"""

from __future__ import annotations

import datetime as dt
import re

from pipeline.models import DateCandidate, DeterministicFields, ParsedEmail

CONTEXT_CHARS = 80

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
_MON = (
    r"(?P<mon>Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|"
    r"Aug(?:ust)?|Sept?(?:ember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?"
)
_ORD = r"(?:st|nd|rd|th)?"
_WD = (
    r"(?P<wd>Mon(?:day)?|Tue(?:s|sday)?|Wed(?:nesday)?|Thu(?:rs|rsday)?|Fri(?:day)?|"
    r"Sat(?:urday)?|Sun(?:day)?)\.?,?\s+"
)
WEEKDAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
# How far back a weekday-qualified date without a year may reach.
WEEKDAY_LOOKBACK_YEARS = 6
_Y = r"(?P<y>(?:19|20)\d\d|'?\d\d)"

# (pattern, kind). Order matters: earlier patterns claim their span first.
PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?<![\d.])(?P<y>(?:19|20)\d\d)[-/.](?P<m>\d\d?)[-/.](?P<d>\d\d?)(?![\d])"), "ymd"),
    (re.compile(rf"\b(?P<d>\d\d?){_ORD}(?:\s+of)?[\s\-/]+{_MON},?[\s\-/]+{_Y}\b", re.I), "dmy_name"),
    (re.compile(rf"\b{_MON}[\s\-]+(?P<d>\d\d?){_ORD},?\s+(?P<y>(?:19|20)\d\d)\b", re.I), "mdy_name"),
    (re.compile(r"(?<![\d.])(?P<a>\d\d?)\.(?P<b>\d\d?)\.(?P<y>(?:19|20)\d\d|\d\d)(?![\d])"), "dotted"),
    (re.compile(r"(?<![\d/])(?P<a>\d\d?)[/-](?P<b>\d\d?)[/-](?P<y>(?:19|20)\d\d|\d\d)(?![\d/])"), "slashed"),
    (re.compile(r"(?<!\d)(?P<y>(?:19|20)\d\d)(?P<m>[01]\d)(?P<d>[0-3]\d)(?!\d)"), "compact"),
    # No year, but the weekday pins it: "Friday, 10 April" -> the latest such year.
    (re.compile(rf"\b{_WD}(?P<d>\d\d?){_ORD}\s+{_MON}(?![\s,\-/]*'?\d)", re.I), "wd_dm"),
    (re.compile(rf"\b{_WD}{_MON}\s+(?P<d>\d\d?){_ORD}\b(?![\s,]*'?\d)", re.I), "wd_md"),
]

_WS = re.compile(r"\s+")


def _year(raw: str) -> int:
    raw = raw.lstrip("'")
    y = int(raw)
    if len(raw) == 2:
        y += 2000 if y < 70 else 1900
    return y


def _iso(y: int, m: int, d: int) -> str | None:
    try:
        return dt.date(y, m, d).isoformat()
    except ValueError:
        return None


def _weekday_year(weekday: int, month: int, day: int, today: dt.date) -> str | None:
    for year in range(today.year, today.year - WEEKDAY_LOOKBACK_YEARS - 1, -1):
        iso = _iso(year, month, day)
        if iso and dt.date.fromisoformat(iso) <= today and dt.date.fromisoformat(iso).weekday() == weekday:
            return iso
    return None


def _interpretations(match: re.Match[str], kind: str, today: dt.date) -> list[str]:
    g = match.groupdict()
    if kind in ("wd_dm", "wd_md"):
        found = [_weekday_year(WEEKDAYS[g["wd"][:3].lower()], MONTHS[g["mon"][:3].lower()],
                               int(g["d"]), today)]
    elif kind in ("ymd", "compact"):
        found = [_iso(int(g["y"]), int(g["m"]), int(g["d"]))]
    elif kind in ("dmy_name", "mdy_name"):
        found = [_iso(_year(g["y"]), MONTHS[g["mon"][:3].lower()], int(g["d"]))]
    else:
        a, b, y = int(g["a"]), int(g["b"]), _year(g["y"])
        dmy, mdy = _iso(y, b, a), _iso(y, a, b)
        # Dots are a day-first convention; slashes are ambiguous, so both
        # readings go to the LLM with their context when both are valid.
        found = [dmy] if kind == "dotted" and dmy else [dmy, mdy]
    out: list[str] = []
    for iso in found:
        if iso and iso not in out:
            out.append(iso)
    return out


def _context(text: str, start: int, end: int) -> str:
    lo, hi = max(0, start - CONTEXT_CHARS), min(len(text), end + CONTEXT_CHARS)
    snippet = _WS.sub(" ", text[lo:hi]).strip()
    return ("..." if lo > 0 else "") + snippet + ("..." if hi < len(text) else "")


def find_date_candidates(texts: list[str], today: dt.date | None = None) -> list[DateCandidate]:
    """Every full date in ``texts`` with its context, in order, once per context.

    ``today`` bounds weekday-only dates ("Friday, 10 April") to the past.
    """
    today = today or dt.date.today()
    seen: set[tuple[str, str]] = set()
    out: list[DateCandidate] = []
    for text in texts:
        claimed: list[tuple[int, int]] = []
        hits: list[tuple[int, int, list[str]]] = []
        for pattern, kind in PATTERNS:
            for m in pattern.finditer(text):
                s, e = m.span()
                if any(s < ce and cs < e for cs, ce in claimed):
                    continue
                isos = _interpretations(m, kind, today)
                if isos:
                    claimed.append((s, e))
                    hits.append((s, e, isos))
        for s, e, isos in sorted(hits):
            ctx = _context(text, s, e)
            for iso in isos:
                if (iso, ctx) not in seen:
                    seen.add((iso, ctx))
                    out.append(DateCandidate(iso=iso, context=ctx))
    return out


def title_from_folder_name(name: str) -> str | None:
    """The folder name when it reads as a subject; None for an ID like ``035239``."""
    cleaned = name.strip()
    words = re.findall(r"[^\W\d_]{2,}", cleaned)
    if len(words) >= 2 or any(len(w) >= 4 for w in words):
        return cleaned
    return None


def extract_deterministic(parsed: ParsedEmail) -> DeterministicFields:
    folder = parsed.folder
    pdf_names = [p.name for p in folder.pdf_paths]
    texts = [parsed.text]
    for name in pdf_names:
        texts.append(f"Attached PDF filename: {name}")
        texts.append(parsed.pdf_texts.get(name, ""))
    return DeterministicFields(
        source_file=folder.source_file,
        pdf_attachment=pdf_names or None,
        folder_name=title_from_folder_name(folder.source_file),
        date_candidates=find_date_candidates(texts),
    )
