import json
from pathlib import Path

import pytest

from pipeline.llm import (
    CachedLLMClient,
    FakeLLMClient,
    LLMClient,
    LLMResponseError,
    cache_key,
    classify_email,
    parse_llm_response,
)
from pipeline.models import (
    DeterministicFields,
    EmailFolder,
    InlineImage,
    LLMResult,
    ParsedEmail,
)

RESULT = LLMResult(
    title="Semis: raising estimates",
    bank="Bank A",
    date_choice="2026-04-09",
    market_wrap=False,
    primary_asset_tag="Equity",
    asset_tags=["Equity", "Company Research"],
    companies_mentioned=["Company A"],
    industry_subindustry=["TECHNOLOGY > Semiconductors"],
)


@pytest.fixture
def image(tmp_path: Path) -> InlineImage:
    p = tmp_path / "chart.png"
    p.write_bytes(b"\x89PNG one")
    return InlineImage(p, "alt: chart")


def test_fake_client_satisfies_protocol():
    fake = FakeLLMClient(RESULT)
    assert isinstance(fake, LLMClient)
    assert fake.classify("s", "u", []) == RESULT
    assert fake.calls == [("s", "u", [])]


def test_fake_client_returns_copies_so_callers_cannot_mutate_it():
    fake = FakeLLMClient(RESULT)
    fake.classify("s", "u", []).asset_tags.append("FX")
    assert fake.classify("s", "u", []).asset_tags == ["Equity", "Company Research"]


def test_fake_client_can_compute_from_prompt():
    fake = FakeLLMClient(lambda s, u, i: RESULT.model_copy(update={"title": u}))
    assert fake.classify("s", "hello", []).title == "hello"


# --- cache ------------------------------------------------------------------------


def test_cache_returns_stored_result_for_identical_content(tmp_path, image):
    fake = FakeLLMClient(RESULT)
    client = CachedLLMClient(fake, tmp_path / "cache")
    first = client.classify("sys", "user", [image])
    second = client.classify("sys", "user", [image])
    assert first == second == RESULT
    assert len(fake.calls) == 1
    assert (client.hits, client.misses) == (1, 1)


def test_cache_survives_a_new_client_instance(tmp_path, image):
    CachedLLMClient(FakeLLMClient(RESULT), tmp_path / "c").classify("s", "u", [image])
    fake = FakeLLMClient(RESULT)
    assert CachedLLMClient(fake, tmp_path / "c").classify("s", "u", [image]) == RESULT
    assert fake.calls == []


@pytest.mark.parametrize("change", ["system", "user", "model", "image_bytes", "image_context"])
def test_cache_misses_on_any_change(tmp_path, image, change):
    base = cache_key("m", "s", "u", [image])
    if change == "system":
        key = cache_key("m", "s2", "u", [image])
    elif change == "user":
        key = cache_key("m", "s", "u2", [image])
    elif change == "model":
        key = cache_key("m2", "s", "u", [image])
    elif change == "image_bytes":
        image.path.write_bytes(b"\x89PNG two")
        key = cache_key("m", "s", "u", [image])
    else:
        key = cache_key("m", "s", "u", [InlineImage(image.path, "alt: other")])
    assert key != base


def test_cache_key_depends_on_image_order(tmp_path):
    a, b = tmp_path / "a.png", tmp_path / "b.png"
    a.write_bytes(b"a")
    b.write_bytes(b"b")
    ia, ib = InlineImage(a, ""), InlineImage(b, "")
    assert cache_key("m", "s", "u", [ia, ib]) != cache_key("m", "s", "u", [ib, ia])


def test_corrupt_cache_entry_is_refetched(tmp_path):
    fake = FakeLLMClient(RESULT)
    client = CachedLLMClient(fake, tmp_path / "c")
    client.classify("s", "u", [])
    entry = next((tmp_path / "c").rglob("*.json"))
    entry.write_text("{not json")
    assert client.classify("s", "u", []) == RESULT
    assert len(fake.calls) == 2


# --- adapter validation ----------------------------------------------------------------


def test_parse_valid_response_from_str_and_dict():
    raw = RESULT.model_dump()
    assert parse_llm_response(json.dumps(raw)) == RESULT
    assert parse_llm_response(raw) == RESULT


@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        "[]",
        json.dumps({**RESULT.model_dump(), "market_wrap": "maybe"}),
        json.dumps({k: v for k, v in RESULT.model_dump().items() if k != "bank"}),
        json.dumps({**RESULT.model_dump(), "asset_tags": "Equity"}),
    ],
)
def test_parse_rejects_responses_that_break_the_schema(raw):
    with pytest.raises(LLMResponseError):
        parse_llm_response(raw)


# --- classify_email ------------------------------------------------------------------------


def test_classify_email_makes_one_call_with_prompt_and_images(tmp_path, image):
    folder = EmailFolder("035239", tmp_path, tmp_path / "emailbody.html")
    parsed = ParsedEmail(folder, text="Email body text", images=[image])
    det = DeterministicFields("035239", None, None, [])
    fake = FakeLLMClient(RESULT)
    assert classify_email(parsed, det, fake) == RESULT
    (system, user, images), = fake.calls
    assert "Market Wrap" in system
    assert "Email body text" in user
    assert images == [image]
