import json

from eval.score import agreement, distribution, main, prf, score


def rec(sf, **kw):
    base = dict(folder_name="T", bank="Bank A", date="2026-04-09", market_wrap="NO",
                primary_asset_tag="Equity", asset_tags=["Equity", "Company Research"],
                companies_mentioned=["Alpha"], industry_subindustry=["TECHNOLOGY > Software"],
                pdf_attachment=None, source_file=sf)
    base.update(kw)
    return base


def by_id(*records):
    return {r["source_file"]: r for r in records}


def test_prf():
    assert prf(2, 1, 1) == {"precision": 0.667, "recall": 0.667, "f1": 0.667, "tp": 2, "fp": 1, "fn": 1}
    assert prf(0, 0, 0)["f1"] == 1.0


def test_perfect_predictions_score_one():
    labels = by_id(rec("1"), rec("2", market_wrap="YES", primary_asset_tag="Market Wrap",
                                  asset_tags=["Market Wrap"], companies_mentioned=[], industry_subindustry=[]))
    s = score(labels, labels)
    assert all(s["fields"][f]["accuracy"] == 1.0 for f in ("folder_name", "bank", "date", "primary_asset_tag", "market_wrap"))
    assert s["fields"]["asset_tags"]["f1"] == 1.0
    assert s["fields"]["market_wrap"]["confusion"]["label_YES_pred_YES"] == 1


def test_errors_are_counted_and_listed():
    labels = by_id(rec("1"), rec("2"))
    pred = by_id(rec("1", bank="  bank a ", date=None, asset_tags=["Equity", "FX"],
                      companies_mentioned=["alpha", "Beta"]),
                 rec("2", market_wrap="YES", primary_asset_tag="Market Wrap"))
    s = score(pred, labels)
    assert s["fields"]["bank"]["accuracy"] == 1.0  # case and spacing ignored
    assert s["fields"]["date"]["accuracy"] == 0.5
    assert s["fields"]["date"]["wrong"] == [{"source_file": "1", "pred": None, "label": "2026-04-09"}]
    assert s["fields"]["market_wrap"]["confusion"]["label_NO_pred_YES"] == 1
    tags = s["fields"]["asset_tags"]
    assert (tags["tp"], tags["fp"], tags["fn"]) == (3, 1, 1)
    assert tags["per_tag"]["FX"]["precision"] == 0.0
    comp = s["fields"]["companies_mentioned"]
    assert (comp["tp"], comp["fp"], comp["fn"]) == (2, 1, 0)


def test_missing_predictions_reported():
    s = score(by_id(rec("1")), by_id(rec("1"), rec("2")))
    assert s["missing_predictions"] == ["2"] and s["scored"] == 1


def test_run_to_run_agreement():
    a = by_id(rec("1"), rec("2"))
    b = by_id(rec("1", asset_tags=["Company Research", "Equity"]), rec("2", bank="Bank B"))
    res = agreement(a, b)
    assert res["compared"] == 2
    assert res["agreement"]["asset_tags"] == 1.0  # order doesn't matter
    assert res["agreement"]["bank"] == 0.5


def test_distribution():
    d = distribution(by_id(rec("1", date=None), rec("2", industry_subindustry=["Unknown"], companies_mentioned=[])))
    assert d["null_date_rate"] == 0.5
    assert d["unknown_industry"] == 1 and d["equity_without_companies"] == 1


def test_cli(tmp_path, capsys):
    pred, labels = tmp_path / "p.json", tmp_path / "l.json"
    pred.write_text(json.dumps([rec("1")]))
    labels.write_text(json.dumps([rec("1")]))
    assert main(["--pred", str(pred), "--labels", str(labels), "--compare", str(pred), "--out", str(tmp_path / "r.json")]) == 0
    report = json.loads((tmp_path / "r.json").read_text())
    assert report["scores"]["fields"]["date"]["accuracy"] == 1.0
    assert report["run_to_run"]["agreement"]["bank"] == 1.0


from eval.make_template import pick, template  # noqa: E402


def test_pick_covers_buckets_and_is_deterministic():
    pred = {}
    for n, tag in enumerate(["Macro", "FX", "Equity", "Market Wrap"] * 5):
        pred[f"{n:03d}"] = rec(f"{n:03d}", primary_asset_tag=tag,
                               date=None if n % 7 == 0 else "2026-04-09",
                               companies_mentioned=["Alpha"] if tag == "Equity" else [])
    log = {"005": {"images": ["a.png"]}}
    ids = pick(pred, log, size=10)
    assert ids == pick(pred, log, size=10)
    assert len(ids) >= 10 and len(set(ids)) == len(ids)
    assert {pred[i]["primary_asset_tag"] for i in ids} == {"Macro", "FX", "Equity", "Market Wrap"}
    assert "005" in ids
    assert any(pred[i]["date"] is None for i in ids)


def test_template_is_blank_ten_field_records():
    (t,) = template(["035239"])
    assert list(t) == ["folder_name", "bank", "date", "market_wrap", "primary_asset_tag", "asset_tags",
                       "companies_mentioned", "industry_subindustry", "pdf_attachment", "source_file"]
    assert t["source_file"] == "035239" and t["bank"] is None and t["asset_tags"] == []
