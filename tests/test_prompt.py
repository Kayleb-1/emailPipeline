import re
from pathlib import Path

import pytest

from pipeline import taxonomy as tx
from pipeline.models import (
    DateCandidate,
    DeterministicFields,
    EmailFolder,
    InlineImage,
    ParsedEmail,
)
from pipeline.prompt import MATERIALITY_DEFINITION, build_prompt


@pytest.fixture
def parsed(tmp_path: Path) -> ParsedEmail:
    folder = EmailFolder("035239", tmp_path, tmp_path / "emailbody.html")
    return ParsedEmail(
        folder=folder,
        text="Bank A Semis: raising estimates for Company A",
        pdf_texts={"note.pdf": "Full PDF body about Company A margins", "scan.pdf": ""},
        images=[
            InlineImage(tmp_path / "inline" / "z.png", "alt: Fig 1 | after: Source: Bank A"),
            InlineImage(tmp_path / "inline" / "a.png", ""),
        ],
    )


@pytest.fixture
def det() -> DeterministicFields:
    return DeterministicFields(
        source_file="035239",
        pdf_attachment=["note.pdf", "scan.pdf"],
        folder_name=None,
        date_candidates=[
            DateCandidate("2026-04-09", "Published 9 April 2026 by the desk"),
            DateCandidate("2026-05-01", "Earnings call on 1 May 2026"),
        ],
    )


def test_system_contains_every_asset_tag_line(parsed, det):
    system, _ = build_prompt(parsed, det)
    for primary, subs in tx.ASSET_TAXONOMY.items():
        assert f"- {primary}: {', '.join(subs) if subs else 'No sub-tags'}" in system


def test_system_contains_every_industry_string(parsed, det):
    system, _ = build_prompt(parsed, det)
    for s in tx.ALL_INDUSTRY_STRINGS:
        assert f"\n- {s}\n" in system
    assert tx.UNKNOWN_INDUSTRY_RULE in system


def test_system_contains_checklist_and_definition_verbatim(parsed, det):
    system, _ = build_prompt(parsed, det)
    for q in tx.MARKET_WRAP_CHECKLIST.values():
        assert f"- {q}" in system
    assert tx.MARKET_WRAP_DEFINITION in system


def test_system_contains_tagging_rules_and_materiality(parsed, det):
    system, _ = build_prompt(parsed, det)
    for rule in tx.ASSET_TAGGING_RULES:
        assert rule in system
    assert MATERIALITY_DEFINITION in system
    assert tx.INDUSTRY_TAGGING_RULE in system
    assert "Format: SECTOR > Subindustry" in system


def test_system_prompt_is_the_same_for_every_email(parsed, det, tmp_path):
    other = ParsedEmail(EmailFolder("x", tmp_path, None), text="other")
    assert build_prompt(parsed, det)[0] == build_prompt(other, det)[0]


def test_user_has_date_candidates_with_context_numbered(parsed, det):
    _, user = build_prompt(parsed, det)
    assert "1. 2026-04-09: Published 9 April 2026 by the desk" in user
    assert "2. 2026-05-01: Earnings call on 1 May 2026" in user


def test_user_says_when_there_are_no_date_candidates(parsed, det):
    det.date_candidates = []
    _, user = build_prompt(parsed, det)
    assert "None found. date_choice must be null." in user


def test_user_has_full_email_and_pdf_text(parsed, det):
    _, user = build_prompt(parsed, det)
    assert parsed.text in user
    assert "## Attached PDF: note.pdf\nFull PDF body about Company A margins" in user
    assert "## Attached PDF: scan.pdf\n(no extractable text)" in user


def test_user_lists_image_contexts_in_order(parsed, det):
    _, user = build_prompt(parsed, det)
    first = user.index("Image 1 (z.png): alt: Fig 1 | after: Source: Bank A")
    second = user.index("Image 2 (a.png): no nearby text")
    assert first < second


def test_no_images_section_without_images(parsed, det):
    parsed.images = []
    _, user = build_prompt(parsed, det)
    assert "Attached images" not in user


def test_folder_name_given_only_when_it_reads_as_a_subject(parsed, det):
    _, user = build_prompt(parsed, det)
    assert "Folder name" not in user
    det.folder_name = "Global Rates Weekly"
    _, user = build_prompt(parsed, det)
    assert user.startswith("Folder name (subject): Global Rates Weekly")


def test_nothing_is_cut_from_long_inputs(parsed, det):
    parsed.text = "word " * 50_000
    _, user = build_prompt(parsed, det)
    assert user.count("word") == 50_000


def test_prompt_mentions_every_output_field(parsed, det):
    system, _ = build_prompt(parsed, det)
    for field in ("market_wrap", "primary_asset_tag", "asset_tags", "companies_mentioned",
                  "industry_subindustry", "title", "bank", "date_choice"):
        assert re.search(rf"\b{field}\b", system), field
