import json
import sqlite3

import pytest

import build_index as cli
from pipeline.index_db import IndexBuildError, build_index
from tests.helpers import make_email, make_pdf

EQUITY = {
    "folder_name": "Semis: raising estimates", "bank": "Bank A", "date": "2026-04-09",
    "market_wrap": "NO", "primary_asset_tag": "Equity",
    "asset_tags": ["Equity", "Company Research", "FX", "USD"],
    "companies_mentioned": ["Company Alpha", "Beta Corp"],
    "industry_subindustry": ["TECHNOLOGY > Semiconductors", "TECHNOLOGY > Hardware"],
    "pdf_attachment": ["a.pdf", "b.pdf"], "source_file": "001",
}
WRAP = {
    "folder_name": "Morning Market Wrap", "bank": "Bank B", "date": None,
    "market_wrap": "YES", "primary_asset_tag": "Market Wrap", "asset_tags": ["Market Wrap"],
    "companies_mentioned": [], "industry_subindustry": [], "pdf_attachment": None,
    "source_file": "002",
}


@pytest.fixture
def setup(tmp_path):
    data = tmp_path / "Data"
    make_email(data, "001", html="<p>Our zygomorphic thesis on Company Alpha.</p>",
               files={"a.pdf": make_pdf([["Quokka supply chain checks"] * 10]),
                      "b.pdf": make_pdf([["Second report body text"] * 10])})
    make_email(data, "002", html="<p>Equities fell, yields rose. Café prices.</p>")
    json_path = tmp_path / "classified_emails.json"
    json_path.write_text(json.dumps([EQUITY, WRAP]))
    return json_path, data, tmp_path / "web" / "data" / "emails.db"


def q(db, sql, *args):
    with sqlite3.connect(db) as conn:
        return conn.execute(sql, args).fetchall()


def test_row_counts_match_json(setup):
    json_path, data, db = setup
    summary = build_index(json_path, data, db)
    assert summary["records"] == 2 and summary["warnings"] == []
    assert q(db, "SELECT count(*) FROM emails") == [(2,)]
    assert q(db, "SELECT count(*) FROM email_fts") == [(2,)]
    assert q(db, "SELECT value FROM meta WHERE key='records'") == [("2",)]


def test_join_tables_are_correct(setup):
    json_path, data, db = setup
    build_index(json_path, data, db)
    assert q(db, "SELECT tag, parent, is_primary FROM email_asset_tags WHERE source_file='001' ORDER BY tag") == [
        ("Company Research", "Equity", 0), ("Equity", None, 1), ("FX", None, 0), ("USD", "FX", 0),
    ]
    assert q(db, "SELECT company FROM email_companies ORDER BY company") == [("Beta Corp",), ("Company Alpha",)]
    assert q(db, "SELECT industry, sector FROM email_industries ORDER BY industry") == [
        ("TECHNOLOGY > Hardware", "TECHNOLOGY"), ("TECHNOLOGY > Semiconductors", "TECHNOLOGY"),
    ]
    assert q(db, "SELECT filename, position FROM email_pdfs ORDER BY position") == [("a.pdf", 0), ("b.pdf", 1)]
    assert q(db, "SELECT date, has_pdf FROM emails WHERE source_file='002'") == [(None, 0)]


def test_record_json_round_trips_the_ten_fields(setup):
    json_path, data, db = setup
    build_index(json_path, data, db)
    (raw,), = q(db, "SELECT record_json FROM emails WHERE source_file='001'")
    assert json.loads(raw) == EQUITY


def test_fts_finds_body_only_and_pdf_only_terms(setup):
    json_path, data, db = setup
    build_index(json_path, data, db)
    match = "SELECT source_file FROM email_fts WHERE email_fts MATCH ?"
    assert q(db, match, "zygomorphic") == [("001",)]
    assert q(db, match, "quokka") == [("001",)]
    assert q(db, match, "cafe") == [("002",)]  # diacritics folded
    assert q(db, match, 'companies:"Beta Corp"') == [("001",)]


def test_rebuild_is_idempotent(setup):
    json_path, data, db = setup
    build_index(json_path, data, db)
    first = q(db, "SELECT * FROM emails ORDER BY source_file")
    build_index(json_path, data, db)
    assert q(db, "SELECT * FROM emails ORDER BY source_file") == first
    assert q(db, "SELECT count(*) FROM email_asset_tags") == [(5,)]


def test_rebuild_reflects_removed_records(setup):
    json_path, data, db = setup
    build_index(json_path, data, db)
    json_path.write_text(json.dumps([WRAP]))
    build_index(json_path, data, db)
    assert q(db, "SELECT source_file FROM emails") == [("002",)]
    assert q(db, "SELECT count(*) FROM email_companies") == [(0,)]


@pytest.mark.parametrize(
    "bad",
    [
        [{**EQUITY, "extra": 1}],
        [{k: v for k, v in EQUITY.items() if k != "bank"}],
        [{**EQUITY, "market_wrap": "yes"}],
        [{**EQUITY, "asset_tags": ["Crypto"]}],
        [EQUITY, EQUITY],
        {"not": "a list"},
    ],
)
def test_rejects_records_that_break_the_schema(setup, bad):
    json_path, data, db = setup
    json_path.write_text(json.dumps(bad))
    with pytest.raises(IndexBuildError):
        build_index(json_path, data, db)
    assert not db.exists()


def test_failed_rebuild_keeps_the_previous_index(setup):
    json_path, data, db = setup
    build_index(json_path, data, db)
    json_path.write_text("{broken")
    with pytest.raises(IndexBuildError):
        build_index(json_path, data, db)
    assert q(db, "SELECT count(*) FROM emails") == [(2,)]


def test_missing_email_folder_is_a_warning(setup):
    json_path, data, db = setup
    json_path.write_text(json.dumps([EQUITY, WRAP, {**WRAP, "source_file": "999"}]))
    summary = build_index(json_path, data, db)
    assert summary["records"] == 3
    assert any("999" in w for w in summary["warnings"])


def test_cli(setup, capsys):
    json_path, data, db = setup
    assert cli.main(["--json", str(json_path), "--data", str(data), "--out", str(db)]) == 0
    assert "indexed 2 emails" in capsys.readouterr().out
    json_path.write_text("[1]")
    assert cli.main(["--json", str(json_path), "--data", str(data), "--out", str(db)]) == 1
