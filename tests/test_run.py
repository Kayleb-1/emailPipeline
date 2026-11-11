import json

import pytest

import classify
from pipeline.llm import FakeLLMClient, LLMResponseError
from pipeline.models import BRIEF_FIELD_ORDER, LLMResult
from pipeline.run import run
from tests.helpers import make_email, make_pdf

PNG = b"\x89PNG\r\n\x1a\nimg"


def result_for(user: str) -> LLMResult:
    """Fake classifier: a wrap if the email says so, else equity on Company Alpha."""
    if "Morning Market Wrap" in user:
        return LLMResult(title="Morning Market Wrap", bank="Bank B", date_choice="2026-04-10",
                         market_wrap=True, primary_asset_tag="Market Wrap",
                         asset_tags=["Market Wrap"], companies_mentioned=[],
                         industry_subindustry=[])
    if "BROKEN" in user:
        raise LLMResponseError("bad response")
    return LLMResult(title="Semis note", bank="Bank A", date_choice="2026-04-09",
                     market_wrap=False, primary_asset_tag="Equity", asset_tags=["Company Research"],
                     companies_mentioned=["Company Alpha", "Made Up Co"],
                     industry_subindustry=["TECHNOLOGY > Semiconductors"])


@pytest.fixture
def data(tmp_path):
    root = tmp_path / "Data"
    make_email(root, "001", html="<p>Bank A, 9 April 2026</p><p>Company Alpha beat.</p>"
                                 '<img src="inline/chart.png">',
               files={"inline/chart.png": PNG, "Note_20260409.pdf": make_pdf([["Company Alpha"] * 40])})
    make_email(root, "002", html="<h1>Morning Market Wrap</h1><p>Friday, 10 April 2026</p>",
               files={"thumbs/t.png": PNG, "model.xlsx": b"x"})
    make_email(root, "003", html=None)
    return root


def read_outputs(tmp_path):
    out = json.loads((tmp_path / "out" / "classified_emails.json").read_text())
    log = [json.loads(line) for line in (tmp_path / "out" / "classification_log.jsonl").read_text().splitlines()]
    flags = json.loads((tmp_path / "out" / "flags.json").read_text())
    return out, log, flags


def test_end_to_end_with_fake_client(tmp_path, data):
    fake = FakeLLMClient(lambda s, u, i: result_for(u))
    summary = run(data, tmp_path / "out" / "classified_emails.json", fake, workers=2)
    out, log, flags = read_outputs(tmp_path)

    assert summary == {"folders": 3, "records": 2, "errors": 0, "skipped": 1, "flags": 3, "bank_renames": 0}
    assert [r["source_file"] for r in out] == ["001", "002"]
    for record in out:
        assert tuple(record) == BRIEF_FIELD_ORDER

    equity, wrap = out
    assert equity["asset_tags"] == ["Equity", "Company Research"]
    assert equity["companies_mentioned"] == ["Company Alpha"]
    assert equity["pdf_attachment"] == ["Note_20260409.pdf"]
    assert equity["date"] == "2026-04-09"
    assert wrap["market_wrap"] == "YES" and wrap["asset_tags"] == ["Market Wrap"]
    assert wrap["pdf_attachment"] is None

    by_source = {e["source_file"]: e for e in log}
    assert by_source["003"]["status"] == "skipped"
    assert by_source["001"]["images"] == ["chart.png"]
    assert any("Made Up Co" in n for n in by_source["001"]["rules"])
    assert {f["reason"] for f in flags} == {"missing_html", "unexpected_file"}

    # one call per email, image passed through
    assert len(fake.calls) == 2
    assert any(len(images) == 1 for _, _, images in fake.calls)


def test_one_failing_email_does_not_stop_the_run(tmp_path, data):
    make_email(data, "004", html="<p>BROKEN</p>")
    summary = run(data, tmp_path / "out" / "classified_emails.json",
                  FakeLLMClient(lambda s, u, i: result_for(u)))
    out, log, _ = read_outputs(tmp_path)
    assert summary["errors"] == 1 and summary["records"] == 2
    assert {e["source_file"]: e["status"] for e in log}["004"] == "error"


def test_cache_makes_second_run_free_and_identical(tmp_path, data):
    fake = FakeLLMClient(lambda s, u, i: result_for(u))
    out = tmp_path / "out" / "classified_emails.json"
    first = run(data, out, fake, cache_dir=tmp_path / "cache")
    text1 = out.read_text()
    second = run(data, out, fake, cache_dir=tmp_path / "cache")
    assert (first["cache_misses"], second["cache_hits"], second["cache_misses"]) == (2, 2, 0)
    assert len(fake.calls) == 2
    assert out.read_text() == text1


def test_only_limits_the_run(tmp_path, data):
    summary = run(data, tmp_path / "out" / "classified_emails.json",
                  FakeLLMClient(lambda s, u, i: result_for(u)), only=["002"])
    assert summary["records"] == 1


def test_cli_main(tmp_path, data, capsys):
    out = tmp_path / "out" / "classified_emails.json"
    code = classify.main(["--data", str(data), "--out", str(out), "--no-cache"],
                         client=FakeLLMClient(lambda s, u, i: result_for(u)))
    assert code == 0
    assert "records=2" in capsys.readouterr().out
    assert len(json.loads(out.read_text())) == 2


def test_cli_missing_data_dir(tmp_path):
    assert classify.main(["--data", str(tmp_path / "nope")], client=FakeLLMClient(None)) == 2


def test_bank_spellings_are_harmonised_across_the_run(tmp_path, data):
    make_email(data, "004", html="<p>Bank A again, 9 April 2026</p>")
    make_email(data, "005", html="<p>Bank A, 9 April 2026, more on Company Alpha</p>")
    def fake(s, u, i):
        r = result_for(u)
        return r.model_copy(update={"bank": "BANK A plc"}) if "again" in u else r
    summary = run(data, tmp_path / "out" / "classified_emails.json", FakeLLMClient(fake))
    out, log, _ = read_outputs(tmp_path)
    assert summary["bank_renames"] == 1
    assert {r["source_file"]: r["bank"] for r in out}["004"] == "Bank A"
    assert any("consistency" in n for n in {e["source_file"]: e for e in log}["004"]["rules"])
