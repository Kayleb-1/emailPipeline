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
    p.write_bytes(b"\x89PNG\r\n\x1a\n one")
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
        image.path.write_bytes(b"\x89PNG\r\n\x1a\n two")
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


# --- Anthropic adapter (no network: a stub SDK) ------------------------------------------

from types import SimpleNamespace  # noqa: E402

from pipeline.llm import (  # noqa: E402
    AnthropicLLMClient,
    image_content,
    llm_json_schema,
    sniff_media_type,
)
from pipeline import taxonomy as tx  # noqa: E402


class StubSDK:
    def __init__(self, text=None, stop_reason="end_turn", content=None):
        self.kwargs = None
        blocks = content if content is not None else [SimpleNamespace(type="text", text=text)]
        self._response = SimpleNamespace(stop_reason=stop_reason, content=blocks,
                                         stop_details=SimpleNamespace(category="cyber"))
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.kwargs = kwargs
        return self._response


def test_sniff_media_type():
    assert sniff_media_type(b"\x89PNG\r\n\x1a\nrest") == "image/png"
    assert sniff_media_type(b"\xff\xd8\xff\xe0") == "image/jpeg"
    assert sniff_media_type(b"GIF87a...") == "image/gif"
    assert sniff_media_type(b"RIFF\x00\x00\x00\x00WEBPVP8") == "image/webp"
    assert sniff_media_type(b"\x01\x00\x00\x00 EMF") is None


def test_schema_is_strict_and_carries_enums():
    schema = llm_json_schema()
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(LLMResult.model_fields)
    assert schema["properties"]["asset_tags"]["items"]["enum"] == tx.ALL_ASSET_TAGS
    assert "title" not in schema["properties"]["bank"]
    assert schema["properties"]["title"] == {"type": "string"}


def test_image_content_labels_sends_and_reports_unsupported(tmp_path):
    png, extless, emf = tmp_path / "a.png", tmp_path / "inline-cid-123", tmp_path / "x.emf"
    png.write_bytes(b"\x89PNG\r\n\x1a\nA")
    extless.write_bytes(b"\xff\xd8\xff\xe0B")
    emf.write_bytes(b"\x01\x00\x00\x00C")
    blocks, warnings = image_content(
        [InlineImage(png, ""), InlineImage(extless, ""), InlineImage(emf, "")]
    )
    kinds = [b["type"] for b in blocks]
    assert kinds == ["text", "image", "text", "image", "text"]
    assert blocks[0]["text"] == "Image 1 (a.png):"
    assert blocks[3]["source"]["media_type"] == "image/jpeg"
    assert "not attached" in blocks[4]["text"]
    assert warnings == ["x.emf: unsupported image format, not sent"]


def test_adapter_request_shape_and_parsed_result(tmp_path, image):
    sdk = StubSDK(text=RESULT.model_dump_json())
    client = AnthropicLLMClient(sdk_client=sdk)
    assert isinstance(client, LLMClient)
    assert client.classify("SYS", "USER", [image]) == RESULT
    kw = sdk.kwargs
    assert kw["model"] == "claude-sonnet-5-5"
    assert kw["system"][0]["text"] == "SYS"
    assert kw["output_config"]["format"]["schema"] == llm_json_schema()
    assert kw["output_config"]["effort"] == "medium"
    assert kw["fallbacks"] == "default" and kw["betas"] == ["server-side-fallback-2026-07-01"]
    assert "temperature" not in kw
    content = kw["messages"][0]["content"]
    assert content[-1] == {"type": "text", "text": "USER"}
    assert content[1]["type"] == "image"


def test_model_id_includes_model_and_effort_for_the_cache():
    a = AnthropicLLMClient(sdk_client=StubSDK(text="{}"), effort="medium")
    b = AnthropicLLMClient(sdk_client=StubSDK(text="{}"), effort="high")
    assert a.model_id != b.model_id


@pytest.mark.parametrize(
    "sdk",
    [
        StubSDK(text="{}"),
        StubSDK(text="not json"),
        StubSDK(text=RESULT.model_dump_json(), stop_reason="refusal"),
        StubSDK(text=RESULT.model_dump_json(), stop_reason="max_tokens"),
        StubSDK(content=[SimpleNamespace(type="thinking", thinking="")]),
    ],
)
def test_adapter_raises_on_unusable_responses(sdk):
    with pytest.raises(LLMResponseError):
        AnthropicLLMClient(sdk_client=sdk).classify("s", "u", [])


# --- Claude Code CLI adapter (subprocess stubbed) -------------------------------------------

from pipeline.llm import (  # noqa: E402
    PROVIDERS,
    ClaudeCodeLLMClient,
    make_client,
    parse_claude_code_output,
)


def _events(*events) -> str:
    return "\n".join(json.dumps(e) for e in events) + "\n"


OK_OUTPUT = _events(
    {"type": "system", "subtype": "init"},
    {"type": "assistant", "message": {}},
    {"type": "result", "subtype": "success", "is_error": False,
     "result": RESULT.model_dump_json(), "structured_output": RESULT.model_dump()},
)


class StubRun:
    def __init__(self, stdout=OK_OUTPUT, stderr="", returncode=0, exc=None):
        self.stdout, self.stderr, self.returncode, self.exc = stdout, stderr, returncode, exc
        self.calls = []

    def __call__(self, cmd, **kw):
        self.calls.append((cmd, kw))
        if self.exc:
            raise self.exc
        return SimpleNamespace(stdout=self.stdout, stderr=self.stderr, returncode=self.returncode)


def test_claude_code_command_is_locked_down_and_sends_images(image):
    run = StubRun()
    client = ClaudeCodeLLMClient(model="haiku", runner=run)
    assert isinstance(client, LLMClient)
    assert client.classify("SYS", "USER", [image]) == RESULT
    (cmd, kw), = run.calls
    assert cmd[:2] == ["claude", "-p"]
    flag = lambda name: cmd[cmd.index(name) + 1]  # noqa: E731
    assert flag("--model") == "haiku"
    assert flag("--tools") == ""
    assert flag("--setting-sources") == ""
    assert flag("--system-prompt") == "SYS"
    assert json.loads(flag("--json-schema")) == llm_json_schema()
    assert "--no-session-persistence" in cmd and "--strict-mcp-config" in cmd
    message = json.loads(kw["input"])
    content = message["message"]["content"]
    assert [b["type"] for b in content] == ["text", "image", "text"]
    assert content[-1]["text"] == "USER"
    assert kw["cwd"] != str(Path.cwd())  # runs from an empty temp folder


def test_claude_code_model_id_feeds_the_cache():
    assert ClaudeCodeLLMClient(model="haiku").model_id != ClaudeCodeLLMClient(model="sonnet").model_id


def test_parse_falls_back_to_result_text():
    out = _events({"type": "result", "subtype": "success", "is_error": False,
                   "result": RESULT.model_dump_json()})
    assert parse_claude_code_output(out) == RESULT


@pytest.mark.parametrize(
    "run",
    [
        StubRun(stdout="", stderr="Not logged in", returncode=1),
        StubRun(stdout=_events({"type": "result", "subtype": "error_max_turns", "is_error": True, "result": "x"})),
        StubRun(stdout=_events({"type": "result", "subtype": "success", "is_error": True,
                                "result": "Claude usage limit reached"})),
        StubRun(stdout=_events({"type": "result", "subtype": "success", "is_error": False,
                                "structured_output": {"bank": "x"}})),
        StubRun(exc=FileNotFoundError("claude")),
        StubRun(exc=TimeoutError("slow")),
    ],
)
def test_claude_code_failures_raise_response_errors(run):
    with pytest.raises(LLMResponseError):
        ClaudeCodeLLMClient(runner=run).classify("s", "u", [])


def test_make_client_by_provider():
    assert isinstance(make_client("claude-code"), ClaudeCodeLLMClient)
    assert make_client("claude-code").model == "haiku"
    assert make_client("claude-code", model="sonnet").model == "sonnet"
    with pytest.raises(ValueError):
        make_client("nope")
    assert set(PROVIDERS) >= {"claude-code", "anthropic"}
