import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from pipeline import taxonomy as tx
from pipeline.models import (
    BRIEF_FIELD_ORDER,
    DateCandidate,
    EmailFolder,
    EmailRecord,
    Flag,
    LLMResult,
)


def record(**overrides) -> dict:
    base = dict(
        folder_name="Semis: raising estimates",
        bank="Bank A",
        date="2026-03-04",
        market_wrap="NO",
        primary_asset_tag="Equity",
        asset_tags=["Equity", "Company Research"],
        companies_mentioned=["Company A"],
        industry_subindustry=["TECHNOLOGY > Semiconductors"],
        pdf_attachment=["note.pdf"],
        source_file="035239",
    )
    base.update(overrides)
    return base


WRAP = dict(
    market_wrap="YES",
    primary_asset_tag="Market Wrap",
    asset_tags=["Market Wrap"],
    companies_mentioned=[],
    industry_subindustry=[],
)

# --- ten fields, brief order ---------------------------------------------------------


def test_field_order_constant_matches_brief():
    assert BRIEF_FIELD_ORDER == (
        "folder_name", "bank", "date", "market_wrap", "primary_asset_tag", "asset_tags",
        "companies_mentioned", "industry_subindustry", "pdf_attachment", "source_file",
    )


def test_serialises_to_exactly_ten_fields_in_brief_order():
    out = EmailRecord(**record()).to_json_dict()
    assert tuple(out) == BRIEF_FIELD_ORDER


def test_json_round_trip_keeps_order_and_nulls():
    rec = EmailRecord(**record(date=None, pdf_attachment=None))
    text = json.dumps(rec.to_json_dict())
    loaded = json.loads(text)
    assert list(loaded) == list(BRIEF_FIELD_ORDER)
    assert loaded["date"] is None and loaded["pdf_attachment"] is None


def test_extra_fields_rejected():
    with pytest.raises(ValidationError):
        EmailRecord(**record(confidence=0.9))


def test_missing_field_rejected():
    data = record()
    del data["bank"]
    with pytest.raises(ValidationError):
        EmailRecord(**data)


# --- market_wrap -----------------------------------------------------------------------


@pytest.mark.parametrize("value", ["yes", "Yes", "Y", True, "TRUE", ""])
def test_market_wrap_only_yes_or_no(value):
    with pytest.raises(ValidationError):
        EmailRecord(**record(market_wrap=value))


def test_market_wrap_yes_with_brief_fields_is_valid():
    rec = EmailRecord(**record(**WRAP))
    assert rec.market_wrap == "YES"


@pytest.mark.parametrize(
    "override",
    [
        {"primary_asset_tag": "Macro", "asset_tags": ["Market Wrap", "Macro"]},
        {"asset_tags": ["Market Wrap", "FX"]},
        {"companies_mentioned": ["Company A"]},
        {"industry_subindustry": ["Unknown"]},
    ],
)
def test_market_wrap_yes_rejects_anything_else(override):
    with pytest.raises(ValidationError):
        EmailRecord(**record(**{**WRAP, **override}))


# --- dates ------------------------------------------------------------------------------


@pytest.mark.parametrize("bad", ["2026-3-4", "04/03/2026", "2026-02-30", "2026-13-01", "20260304"])
def test_date_must_be_real_yyyy_mm_dd(bad):
    with pytest.raises(ValidationError):
        EmailRecord(**record(date=bad))


def test_date_may_be_null():
    assert EmailRecord(**record(date=None)).date is None


# --- allowed values and brief rules --------------------------------------------------------


def test_unknown_asset_tag_rejected():
    with pytest.raises(ValidationError):
        EmailRecord(**record(asset_tags=["Equity", "Crypto"]))


def test_sub_tag_cannot_be_primary():
    with pytest.raises(ValidationError):
        EmailRecord(**record(primary_asset_tag="USD", asset_tags=["FX", "USD"],
                             companies_mentioned=[], industry_subindustry=[]))


def test_primary_must_be_in_asset_tags():
    with pytest.raises(ValidationError):
        EmailRecord(**record(primary_asset_tag="Macro"))


def test_sub_tag_requires_parent():
    with pytest.raises(ValidationError):
        EmailRecord(**record(primary_asset_tag="Equity",
                             asset_tags=["Equity", "USD"]))


def test_companies_and_industries_are_equity_only():
    with pytest.raises(ValidationError):
        EmailRecord(**record(primary_asset_tag="FX", asset_tags=["FX", "USD"],
                             industry_subindustry=[]))
    with pytest.raises(ValidationError):
        EmailRecord(**record(primary_asset_tag="FX", asset_tags=["FX", "USD"],
                             companies_mentioned=[]))


def test_non_equity_with_empty_lists_is_valid():
    rec = EmailRecord(**record(primary_asset_tag="FX", asset_tags=["FX", "USD"],
                               companies_mentioned=[], industry_subindustry=[]))
    assert rec.asset_tags == ["FX", "USD"]


def test_industry_strings_must_be_from_brief():
    with pytest.raises(ValidationError):
        EmailRecord(**record(industry_subindustry=["Semiconductors"]))
    assert EmailRecord(**record(industry_subindustry=["Unknown"])).industry_subindustry == [
        "Unknown"
    ]


def test_pdf_attachment_is_list_or_null_never_empty():
    with pytest.raises(ValidationError):
        EmailRecord(**record(pdf_attachment=[]))
    with pytest.raises(ValidationError):
        EmailRecord(**record(pdf_attachment="note.pdf"))


# --- LLMResult -------------------------------------------------------------------------------


def llm(**overrides) -> dict:
    base = dict(
        title="T", bank="Bank A", date_choice=None, market_wrap=False,
        primary_asset_tag="Equity", asset_tags=["Equity"], companies_mentioned=[],
        industry_subindustry=[],
    )
    base.update(overrides)
    return base


def test_llm_schema_carries_brief_enums():
    schema = LLMResult.model_json_schema()
    props = schema["properties"]
    assert props["primary_asset_tag"]["enum"] == tx.PRIMARY_ASSET_TAGS
    assert props["asset_tags"]["items"]["enum"] == tx.ALL_ASSET_TAGS
    assert props["industry_subindustry"]["items"]["enum"] == tx.ALL_INDUSTRY_STRINGS
    assert props["market_wrap"]["type"] == "boolean"


def test_llm_result_parses_stray_values_so_rules_can_drop_them():
    res = LLMResult(**llm(asset_tags=["Equity", "Crypto"]))
    assert res.asset_tags == ["Equity", "Crypto"]


def test_llm_result_requires_every_field():
    data = llm()
    del data["bank"]
    with pytest.raises(ValidationError):
        LLMResult(**data)


# --- dataclasses -------------------------------------------------------------------------------


def test_dataclasses_construct_with_prd_fields(tmp_path: Path):
    folder = EmailFolder(source_file="x", path=tmp_path, html_path=None)
    assert folder.pdf_paths == [] and folder.inline_dir is None
    assert Flag("x", "x/thumbs/a.png", "unexpected_file").reason == "unexpected_file"
    assert DateCandidate("2026-03-04", "Published 4 March 2026") == DateCandidate(
        "2026-03-04", "Published 4 March 2026"
    )
