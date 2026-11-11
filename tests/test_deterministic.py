from pathlib import Path

import datetime as dt

import pytest

from pipeline.deterministic import (
    extract_deterministic,
    find_date_candidates,
    title_from_folder_name,
)
from pipeline.models import EmailFolder, ParsedEmail


def isos(text: str) -> list[str]:
    return [c.iso for c in find_date_candidates([text])]


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Published 2026-04-09 by the desk", "2026-04-09"),
        ("Published 2026/4/9", "2026-04-09"),
        ("Daily note, 9 April 2026", "2026-04-09"),
        ("Daily note, 09 Apr 2026", "2026-04-09"),
        ("Daily note, 9th of April, 2026", "2026-04-09"),
        ("Run - Credit Linked Notes 07-Apr-26", "2026-04-07"),
        ("Thursday, April 9, 2026", "2026-04-09"),
        ("Sept 30th 2026", "2026-09-30"),
        ("Insights 09.04.2026", "2026-04-09"),
        ("Insights 13.04.26", "2026-04-13"),
        ("Report as of 2/14/2025", "2025-02-14"),
        ("Report as of 11/17/25", "2025-11-17"),
        ("DailyTechIndex_20260409_en.pdf", "2026-04-09"),
    ],
)
def test_common_formats_normalised(text, expected):
    assert isos(text) == [expected]


def test_ambiguous_slash_date_gives_both_readings():
    assert isos("Meeting on 4/3/2026") == ["2026-03-04", "2026-04-03"]


def test_ambiguous_dotted_date_is_day_first():
    assert isos("Stand 04.03.2026") == ["2026-03-04"]


def test_dotted_falls_back_to_month_first_when_day_first_impossible():
    assert isos("on 04.15.2026") == ["2026-04-15"]


@pytest.mark.parametrize(
    "text",
    ["30 February 2026", "2026-02-30", "2026-13-01", "31/31/2026", "32.01.2026",
     "20261345", "April 2026", "10 April", "version 1.2.3", "ISIN NL0014559478",
     "tel +44 20 7123 4567", "price 1/2/3"],
)
def test_impossible_or_partial_dates_rejected(text):
    assert isos(text) == []


TODAY = dt.date(2026, 11, 11)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Listen to today's Friday, 10 April update", "2026-04-10"),
        ("Mon 13th April: weekly call", "2026-04-13"),
        ("Thursday, April 9 recap", "2026-04-09"),
        ("Saturday 10 April", "2021-04-10"),  # 2021 is the latest Saturday 10 April
    ],
)
def test_weekday_pins_the_year_when_missing(text, expected):
    assert [c.iso for c in find_date_candidates([text], today=TODAY)] == [expected]


def test_weekday_date_never_in_the_future():
    # Friday 10 April falls in 2026; with today before that, it resolves to 2020.
    cands = find_date_candidates(["Friday, 10 April"], today=dt.date(2026, 1, 1))
    assert [c.iso for c in cands] == ["2020-04-10"]


def test_weekday_with_year_uses_the_year_once():
    assert isos("Friday, 10 April 2026") == ["2026-04-10"]
    assert isos("Friday, April 10, 2026") == ["2026-04-10"]


def test_context_shows_surrounding_text():
    text = "Sent: Friday, April 10, 2026 7:02 AM\nSubject: Rates weekly"
    (cand,) = find_date_candidates([text])
    assert cand.iso == "2026-04-10"
    assert "Sent:" in cand.context and "Rates weekly" in cand.context


def test_context_is_bounded_with_ellipses():
    text = "x" * 300 + " 9 April 2026 " + "y" * 300
    (cand,) = find_date_candidates([text])
    assert cand.context.startswith("...") and cand.context.endswith("...")
    assert len(cand.context) < 200


def test_duplicates_kept_once_per_context():
    text = "Published 9 April 2026."
    cands = find_date_candidates([text, text, "Event on 9 April 2026 in London"])
    assert [c.iso for c in cands] == ["2026-04-09", "2026-04-09"]
    assert len({c.context for c in cands}) == 2


def test_same_date_twice_in_one_text_with_different_context():
    text = "Published 9 April 2026. " + "filler " * 40 + "Next call 9 April 2026."
    assert len(find_date_candidates([text])) == 2


def test_document_order_kept():
    assert isos("first 10-Apr-26 then 2026-01-02 then April 3, 2026") == [
        "2026-04-10", "2026-01-02", "2026-04-03",
    ]


def test_iso_date_not_double_counted_by_other_patterns():
    assert isos("2026-04-09") == ["2026-04-09"]


# --- title -----------------------------------------------------------------------


@pytest.mark.parametrize("name", ["035239", "  035239 ", "MSG-00123", "A1", "2026_04_09"])
def test_ids_are_not_titles(name):
    assert title_from_folder_name(name) is None


@pytest.mark.parametrize(
    "name", ["Semis raising estimates", "Global Rates Weekly", "Outlook", "FX Daily 9 Apr"]
)
def test_readable_subjects_are_titles(name):
    assert title_from_folder_name(name) == name


# --- extract_deterministic ----------------------------------------------------------


def test_extract_deterministic_fills_certain_fields(tmp_path: Path):
    pdf = tmp_path / "Weekly_20260410_en.pdf"
    folder = EmailFolder("035239", tmp_path, tmp_path / "emailbody.html", [pdf], None)
    parsed = ParsedEmail(
        folder=folder,
        text="Rates weekly, 9 April 2026",
        pdf_texts={pdf.name: "As of 8 April 2026"},
    )
    det = extract_deterministic(parsed)
    assert det.source_file == "035239"
    assert det.pdf_attachment == ["Weekly_20260410_en.pdf"]
    assert det.folder_name is None
    assert [c.iso for c in det.date_candidates] == ["2026-04-09", "2026-04-10", "2026-04-08"]
    assert "Attached PDF filename" in det.date_candidates[1].context


def test_extract_deterministic_without_pdfs(tmp_path: Path):
    folder = EmailFolder("Global Rates Weekly", tmp_path, tmp_path / "emailbody.html")
    det = extract_deterministic(ParsedEmail(folder=folder, text="no dates here"))
    assert det.pdf_attachment is None
    assert det.folder_name == "Global Rates Weekly"
    assert det.date_candidates == []
