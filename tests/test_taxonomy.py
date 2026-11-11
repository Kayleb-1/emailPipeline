"""The taxonomy constants must match the brief word for word.

The expected text comes from tests/fixtures/brief_excerpt.txt (extracted from the
brief PDF), not from a second hand-typed copy, so a typo can't hide in both.
"""

import re

import pytest

from pipeline import taxonomy as tx


def _norm(text: str) -> str:
    """Collapse PDF line wraps and runs of whitespace into single spaces."""
    return re.sub(r"\s+", " ", text).strip()


@pytest.fixture(scope="module")
def brief(fixtures_dir) -> str:
    raw = (fixtures_dir / "brief_excerpt.txt").read_text(encoding="utf-8")
    return raw.split("---\n", 1)[1]


def _section(brief: str, start: str, end: str) -> str:
    return _norm(brief[brief.index(start) + len(start) : brief.index(end)])


# --- asset tags ---------------------------------------------------------------


def test_asset_table_matches_brief_exactly(brief):
    table = _section(brief, "Primary Asset Class Sub-Asset Classes", "Important tagging rules:")
    expected = " ".join(
        f"{primary} {', '.join(subs) if subs else 'No sub-tags'}"
        for primary, subs in tx.ASSET_TAXONOMY.items()
    )
    assert table == expected


def test_seven_primary_classes_in_brief_order():
    assert tx.PRIMARY_ASSET_TAGS == [
        "Macro", "Fixed Income", "Equity", "Commodities", "FX", "Thematics", "Market Wrap",
    ]


def test_sub_to_parent_covers_every_sub_tag():
    every_sub = [s for subs in tx.ASSET_TAXONOMY.values() for s in subs]
    assert sorted(tx.SUB_TO_PARENT) == sorted(every_sub)
    for parent, subs in tx.ASSET_TAXONOMY.items():
        for sub in subs:
            assert tx.SUB_TO_PARENT[sub] == parent


def test_sub_to_parent_examples():
    assert tx.SUB_TO_PARENT["USD"] == "FX"
    assert tx.SUB_TO_PARENT["Securitisation"] == "Fixed Income"
    assert tx.SUB_TO_PARENT["Energy"] == "Commodities"


def test_all_asset_tags_is_primaries_then_subs_without_duplicates():
    assert tx.ALL_ASSET_TAGS[: len(tx.PRIMARY_ASSET_TAGS)] == tx.PRIMARY_ASSET_TAGS
    assert len(tx.ALL_ASSET_TAGS) == len(set(tx.ALL_ASSET_TAGS)) == 7 + 17


def test_ambiguous_sub_tag_is_rejected():
    with pytest.raises(ValueError):
        tx._sub_to_parent({"A": ["X"], "B": ["X"]})
    with pytest.raises(ValueError):
        tx._sub_to_parent({"A": ["B"], "B": []})


def test_asset_tagging_rules_verbatim(brief):
    text = _norm(brief)
    for rule in tx.ASSET_TAGGING_RULES:
        assert _norm(rule) in text


# --- industry tags --------------------------------------------------------------


def test_industry_table_matches_brief_exactly(brief):
    table = _section(brief, "Industry Subindustries", tx.UNKNOWN_INDUSTRY_RULE)
    expected = " ".join(
        f"{sector} {'; '.join(subs)}" for sector, subs in tx.INDUSTRY_TAXONOMY.items()
    )
    assert table == expected


def test_eleven_sectors():
    assert len(tx.INDUSTRY_TAXONOMY) == 11


def test_industry_strings_use_sector_gt_subindustry_format():
    assert "TECHNOLOGY > Semiconductors" in tx.ALL_INDUSTRY_STRINGS
    assert "CONSUMER CYCLICALS > Textile, Apparel & Footwear" in tx.ALL_INDUSTRY_STRINGS
    for s in tx.ALL_INDUSTRY_STRINGS[:-1]:
        sector, sub = s.split(" > ")
        assert sub in tx.INDUSTRY_TAXONOMY[sector]


def test_repeated_subindustries_stay_distinct_by_sector():
    assert "CONSUMER STAPLES > Retail" in tx.ALL_INDUSTRY_STRINGS
    assert "CONSUMER CYCLICALS > Retail" in tx.ALL_INDUSTRY_STRINGS
    assert "ENERGY > Gas" in tx.ALL_INDUSTRY_STRINGS
    assert "UTILITIES > Gas" in tx.ALL_INDUSTRY_STRINGS


def test_industry_strings_complete_unique_and_end_with_unknown():
    total = sum(len(subs) for subs in tx.INDUSTRY_TAXONOMY.values())
    assert len(tx.ALL_INDUSTRY_STRINGS) == len(set(tx.ALL_INDUSTRY_STRINGS)) == total + 1
    assert tx.ALL_INDUSTRY_STRINGS[-1] == "Unknown"


def test_industry_rules_verbatim(brief):
    text = _norm(brief)
    assert _norm(tx.INDUSTRY_TAGGING_RULE) in text
    assert _norm(tx.UNKNOWN_INDUSTRY_RULE) in text
    assert "Format: SECTOR > Subindustry" in text


# --- market wrap -------------------------------------------------------------------


def test_sixteen_checklist_entries():
    assert len(tx.MARKET_WRAP_CHECKLIST) == 16


def test_checklist_ids_match_prd():
    assert list(tx.MARKET_WRAP_CHECKLIST) == [
        "structure_multi_region", "structure_geo_sections", "structure_markets_in_sequence",
        "structure_short_bullets", "assets_multiple_classes", "assets_brief_coverage",
        "timeframe_previous_session", "timeframe_recent_moves", "purpose_descriptive",
        "purpose_no_forward_view", "title_wrap_terms", "language_summary_style",
        "language_short_statements", "language_consistently_descriptive",
        "depth_brief_topics", "depth_unrelated_updates",
    ]


def test_checklist_questions_verbatim_and_in_brief_order(brief):
    checklist = _section(brief, "Checklist Question", "If Market Wrap = NO")
    questions = [q.strip() for q in re.split(r"(?:^| )- (?=[A-Z])", checklist)[1:]]
    # The category label (e.g. "Asset Coverage") trails the previous question.
    labels = ("Asset Coverage", "Timeframe", "Purpose", "Title", "Language", "Depth")
    for label in labels:
        questions = [q.removesuffix(" " + label) for q in questions]
    assert questions == list(tx.MARKET_WRAP_CHECKLIST.values())


def test_market_wrap_definition_verbatim(brief):
    assert _norm(tx.MARKET_WRAP_DEFINITION) in _norm(brief)


def test_named_constants_are_in_the_taxonomy():
    assert tx.MARKET_WRAP in tx.ASSET_TAXONOMY
    assert tx.EQUITY in tx.ASSET_TAXONOMY
