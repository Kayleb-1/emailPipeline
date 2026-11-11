import pytest

from pipeline.models import DateCandidate, DeterministicFields, LLMResult
from pipeline.rules import RulesError, enforce_rules, verify_companies

CORPUS = (
    "Bank A raises estimates for Company Alpha Inc. after strong results. "
    "We also like Beta & Co on valuation. Peers such as Gamma trade at 12x."
)


def det(**kw) -> DeterministicFields:
    base = dict(
        source_file="035239",
        pdf_attachment=["note.pdf"],
        folder_name=None,
        date_candidates=[DateCandidate("2026-04-09", "Published 9 April 2026")],
    )
    base.update(kw)
    return DeterministicFields(**base)


def llm(**kw) -> LLMResult:
    base = dict(
        title="Semis: raising estimates",
        bank="Bank A",
        date_choice="2026-04-09",
        market_wrap=False,
        primary_asset_tag="Equity",
        asset_tags=["Equity", "Company Research"],
        companies_mentioned=["Company Alpha"],
        industry_subindustry=["TECHNOLOGY > Semiconductors"],
    )
    base.update(kw)
    return LLMResult(**base)


def run(d=None, l=None, corpus=CORPUS):
    notes: list[str] = []
    rec = enforce_rules(d or det(), l or llm(), corpus, notes)
    return rec, notes


def test_clean_result_passes_through_unchanged():
    rec, notes = run()
    assert notes == []
    assert rec.to_json_dict() == {
        "folder_name": "Semis: raising estimates",
        "bank": "Bank A",
        "date": "2026-04-09",
        "market_wrap": "NO",
        "primary_asset_tag": "Equity",
        "asset_tags": ["Equity", "Company Research"],
        "companies_mentioned": ["Company Alpha"],
        "industry_subindustry": ["TECHNOLOGY > Semiconductors"],
        "pdf_attachment": ["note.pdf"],
        "source_file": "035239",
    }


# --- rule 1 ------------------------------------------------------------------------


def test_rule1_market_wrap_yes_sets_fixed_fields():
    rec, notes = run(l=llm(market_wrap=True, primary_asset_tag="Macro",
                           asset_tags=["Macro", "FX", "USD"]))
    assert rec.market_wrap == "YES"
    assert rec.primary_asset_tag == "Market Wrap"
    assert rec.asset_tags == ["Market Wrap"]
    assert rec.companies_mentioned == [] and rec.industry_subindustry == []
    assert any(n.startswith("rule 1") for n in notes)


def test_rule1_short_circuits_everything_else():
    # Unknown tags, unverifiable companies and bad industries would trigger
    # rules 2 to 7; a wrap must skip them all.
    rec, notes = run(l=llm(market_wrap=True, asset_tags=["Crypto", "USD"],
                           companies_mentioned=["Nobody Corp"],
                           industry_subindustry=["Semis"]))
    assert rec.asset_tags == ["Market Wrap"]
    assert not any(n.startswith(("rule 2", "rule 3", "rule 4", "rule 5", "rule 6", "rule 7"))
                   for n in notes)


def test_rule1_still_keeps_date_and_deterministic_fields():
    rec, _ = run(l=llm(market_wrap=True))
    assert rec.date == "2026-04-09"
    assert rec.pdf_attachment == ["note.pdf"] and rec.source_file == "035239"


def test_rule1_wrap_primary_with_no_other_tags_is_treated_as_yes():
    rec, notes = run(l=llm(market_wrap=False, primary_asset_tag="Market Wrap",
                           asset_tags=["Market Wrap"]))
    assert rec.market_wrap == "YES"
    assert any("treated as YES" in n for n in notes)


# --- rule 2 ---------------------------------------------------------------------------


def test_rule2_drops_tags_not_in_the_brief():
    rec, notes = run(l=llm(asset_tags=["Equity", "Crypto", "Company Research", "equity"]))
    assert rec.asset_tags == ["Equity", "Company Research"]
    assert any("rule 2" in n and "Crypto" in n for n in notes)


def test_rule2_drops_market_wrap_tag_when_not_a_wrap():
    rec, notes = run(l=llm(asset_tags=["Equity", "Market Wrap"]))
    assert rec.asset_tags == ["Equity"]
    assert any("Market Wrap tag" in n for n in notes)


# --- rule 3 ------------------------------------------------------------------------------


def test_rule3_sub_tag_brings_in_parent():
    rec, notes = run(l=llm(primary_asset_tag="FX", asset_tags=["USD"],
                           companies_mentioned=[], industry_subindustry=[]))
    assert rec.asset_tags == ["FX", "USD"]
    assert any("rule 3" in n for n in notes)


def test_rule3_tags_come_out_in_brief_order():
    rec, _ = run(l=llm(asset_tags=["JPY", "Company Research", "Rates Strategy", "Equity"]))
    assert rec.asset_tags == [
        "Fixed Income", "Rates Strategy", "Equity", "Company Research", "FX", "JPY",
    ]


# --- rule 4 ---------------------------------------------------------------------------------


def test_rule4_primary_added_to_asset_tags():
    rec, notes = run(l=llm(primary_asset_tag="Macro", asset_tags=["Equity"]))
    assert rec.primary_asset_tag == "Macro"
    assert "Macro" in rec.asset_tags
    assert any("added primary" in n for n in notes)


def test_rule4_sub_tag_as_primary_becomes_its_parent():
    rec, notes = run(l=llm(primary_asset_tag="Securitisation", asset_tags=["Securitisation"],
                           companies_mentioned=[], industry_subindustry=[]))
    assert rec.primary_asset_tag == "Fixed Income"
    assert rec.asset_tags == ["Fixed Income", "Securitisation"]


def test_rule4_invalid_primary_falls_back_to_first_primary_in_tags():
    rec, notes = run(l=llm(primary_asset_tag="Crypto", asset_tags=["Commodities", "Metals"],
                           companies_mentioned=[], industry_subindustry=[]))
    assert rec.primary_asset_tag == "Commodities"
    assert any("invalid" in n for n in notes)


def test_rule4_wrap_primary_on_a_non_wrap_uses_another_class():
    rec, _ = run(l=llm(primary_asset_tag="Market Wrap", asset_tags=["Macro", "Market Wrap"],
                       companies_mentioned=[], industry_subindustry=[]))
    assert rec.market_wrap == "NO" and rec.primary_asset_tag == "Macro"


def test_rule4_nothing_usable_raises():
    with pytest.raises(RulesError):
        run(l=llm(primary_asset_tag="Crypto", asset_tags=["Crypto"]))


# --- rule 5 ---------------------------------------------------------------------------------


def test_rule5_no_equity_clears_companies_and_industries():
    rec, notes = run(l=llm(primary_asset_tag="Fixed Income",
                           asset_tags=["Fixed Income", "Credit Strategy"]))
    assert rec.companies_mentioned == [] and rec.industry_subindustry == []
    assert any(n.startswith("rule 5") for n in notes)


def test_rule5_no_note_when_already_empty():
    _, notes = run(l=llm(primary_asset_tag="Macro", asset_tags=["Macro"],
                         companies_mentioned=[], industry_subindustry=[]))
    assert notes == []


# --- rule 6 ---------------------------------------------------------------------------------


def test_rule6_drops_unknown_industry_strings():
    rec, notes = run(l=llm(industry_subindustry=["TECHNOLOGY > Semiconductors", "Semis",
                                                 "TECHNOLOGY > Semiconductors"]))
    assert rec.industry_subindustry == ["TECHNOLOGY > Semiconductors"]
    assert any("rule 6" in n and "Semis" in n for n in notes)


def test_rule6_none_left_becomes_unknown():
    rec, notes = run(l=llm(industry_subindustry=["Chips"]))
    assert rec.industry_subindustry == ["Unknown"]
    rec, _ = run(l=llm(industry_subindustry=[]))
    assert rec.industry_subindustry == ["Unknown"]


def test_rule6_unknown_dropped_next_to_known_industries():
    rec, _ = run(l=llm(industry_subindustry=["Unknown", "ENERGY > Oil"]))
    assert rec.industry_subindustry == ["ENERGY > Oil"]


# --- rule 7 -------------------------------------------------------------------------------


def test_rule7_drops_companies_not_in_text():
    rec, notes = run(l=llm(companies_mentioned=["Company Alpha", "Invented Holdings"]))
    assert rec.companies_mentioned == ["Company Alpha"]
    assert any("rule 7" in n and "Invented Holdings" in n for n in notes)


def test_verify_companies_matching():
    corpus = "Siemens AG beat; L’Oréal margins; AT&amp;T guidance; Metadata vendors; BETA & CO"
    assert verify_companies(
        ["Siemens", "Siemens AG", "L'Oréal", "AT&T", "Meta", "Beta & Co", "beta & co", "  "],
        corpus,
    ) == ["Siemens", "Siemens AG", "L'Oréal", "AT&T", "Beta & Co"]


def test_verify_companies_allows_added_legal_suffix():
    assert verify_companies(["Company Alpha Inc.", "Gamma plc"], "Company Alpha and Gamma") == [
        "Company Alpha Inc.", "Gamma plc",
    ]


def test_verify_companies_respects_word_boundaries():
    assert verify_companies(["Arm"], "results from ARM, the chip designer") == ["Arm"]
    assert verify_companies(["Arm"], "the arms race") == []
    assert verify_companies(["Arm"], "pharma alarming") == []


# --- rule 8 --------------------------------------------------------------------------------


def test_rule8_date_must_be_a_candidate():
    rec, notes = run(l=llm(date_choice="2026-04-10"))
    assert rec.date is None
    assert any(n.startswith("rule 8") for n in notes)


def test_rule8_null_choice_stays_null_without_note():
    rec, notes = run(l=llm(date_choice=None))
    assert rec.date is None and notes == []


def test_rule8_no_candidates_means_null():
    rec, _ = run(d=det(date_candidates=[]), l=llm(date_choice="2026-04-09"))
    assert rec.date is None


# --- other fields ----------------------------------------------------------------------------


def test_folder_name_prefers_readable_folder_then_llm_title():
    rec, _ = run(d=det(folder_name="Global Rates Weekly"))
    assert rec.folder_name == "Global Rates Weekly"
    rec, _ = run(l=llm(title="  "))
    assert rec.folder_name == "035239"


def test_blank_bank_becomes_unknown():
    rec, _ = run(l=llm(bank=" "))
    assert rec.bank == "Unknown"


def test_no_pdfs_gives_null_attachment():
    rec, _ = run(d=det(pdf_attachment=None))
    assert rec.pdf_attachment is None
