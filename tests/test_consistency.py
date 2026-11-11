from pipeline.consistency import bank_key, canonical_banks, harmonise_banks
from pipeline.models import EmailRecord


def test_bank_key_ignores_case_accents_punctuation_and_generic_words():
    assert bank_key("J.P. Morgan") == bank_key("JPMorgan") == "jpmorgan"
    assert bank_key("Bank J. Safra Sarasin") == bank_key("J. Safra Sarasin")
    assert bank_key("EFG Asset Management") == bank_key("EFG")
    assert bank_key("Société Générale") == bank_key("Societe Generale")
    assert bank_key("Bank") == "bank"  # never empty


def test_variants_take_the_most_frequent_spelling():
    names = ["Union Bancaire Privée"] * 5 + ["UBP"] * 4 + ["J.P. Morgan", "JPMorgan", "JPMorgan"]
    m = canonical_banks(names)
    assert m["UBP"] == "Union Bancaire Privée"
    assert m["J.P. Morgan"] == "JPMorgan"


def test_distinct_banks_stay_distinct():
    m = canonical_banks(["UBS", "UBP", "Union Bancaire Privée", "Barclays", "BNP Paribas", "Deutsche Bank"])
    assert m["UBS"] == "UBS"
    assert m["Barclays"] == "Barclays"
    assert m["Deutsche Bank"] == "Deutsche Bank"
    assert m["BNP Paribas"] == "BNP Paribas"


def test_ties_prefer_the_longer_name():
    assert canonical_banks(["EFG", "EFG Asset Management"])["EFG"] == "EFG Asset Management"


def _rec(sf, bank):
    return EmailRecord(folder_name="t", bank=bank, date=None, market_wrap="NO", primary_asset_tag="Macro",
                       asset_tags=["Macro"], companies_mentioned=[], industry_subindustry=[],
                       pdf_attachment=None, source_file=sf)


def test_harmonise_banks_rewrites_records_and_reports_renames():
    recs = [_rec("1", "UBP"), _rec("2", "Union Bancaire Privée"), _rec("3", "Union Bancaire Privée"), _rec("4", "UBS")]
    out, changed = harmonise_banks(recs)
    assert [r.bank for r in out] == ["Union Bancaire Privée"] * 3 + ["UBS"]
    assert changed == {"UBP": "Union Bancaire Privée"}
    assert recs[0].bank == "UBP"  # inputs untouched
