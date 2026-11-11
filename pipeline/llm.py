"""The LLM boundary: one protocol, a fake for tests, a content-hash cache.

Every provider adapter implements ``LLMClient`` and must support image input
and structured output. Responses are validated against ``LLMResult`` before
anything else sees them. The cache key covers the model, both prompts and the
bytes of every image, so re-runs are free and identical, and any change misses.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import ValidationError

from pipeline.models import DeterministicFields, InlineImage, LLMResult, ParsedEmail
from pipeline.prompt import build_prompt


class LLMResponseError(RuntimeError):
    """The provider's response didn't match the LLMResult schema."""


@runtime_checkable
class LLMClient(Protocol):
    model_id: str

    def classify(self, system: str, user: str, images: list[InlineImage]) -> LLMResult: ...


def parse_llm_response(raw: str | dict) -> LLMResult:
    """Validate a provider's raw structured output. Adapters call this."""
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
        return LLMResult.model_validate(data)
    except (json.JSONDecodeError, ValidationError, TypeError) as exc:
        raise LLMResponseError(f"response does not match LLMResult: {exc}") from exc


class FakeLLMClient:
    """Test double: returns a fixed result, or one computed from the prompt."""

    model_id = "fake"

    def __init__(self, result: LLMResult | Callable[[str, str, list[InlineImage]], LLMResult]):
        self._result = result
        self.calls: list[tuple[str, str, list[InlineImage]]] = []

    def classify(self, system: str, user: str, images: list[InlineImage]) -> LLMResult:
        self.calls.append((system, user, list(images)))
        if callable(self._result):
            return self._result(system, user, images)
        return self._result.model_copy(deep=True)


def cache_key(model_id: str, system: str, user: str, images: list[InlineImage]) -> str:
    h = hashlib.sha256()
    for part in (model_id, system, user):
        h.update(part.encode("utf-8"))
        h.update(b"\x00")
    for img in images:
        h.update(img.path.name.encode("utf-8"))
        h.update(b"\x00")
        h.update(img.context.encode("utf-8"))
        h.update(b"\x00")
        h.update(hashlib.sha256(img.path.read_bytes()).digest())
    return h.hexdigest()


class CachedLLMClient:
    """Wraps a client; stores each validated result as JSON under ``cache_dir``."""

    def __init__(self, inner: LLMClient, cache_dir: Path):
        self.inner = inner
        self.model_id = inner.model_id
        self.cache_dir = cache_dir
        self.hits = 0
        self.misses = 0

    def _path(self, key: str) -> Path:
        return self.cache_dir / key[:2] / f"{key}.json"

    def classify(self, system: str, user: str, images: list[InlineImage]) -> LLMResult:
        path = self._path(cache_key(self.model_id, system, user, images))
        if path.exists():
            try:
                result = LLMResult.model_validate_json(path.read_text(encoding="utf-8"))
                self.hits += 1
                return result
            except ValidationError:
                pass  # stale or corrupt entry: fetch again and overwrite
        self.misses += 1
        result = self.inner.classify(system, user, images)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        tmp.replace(path)
        return result


def classify_email(
    parsed: ParsedEmail, det: DeterministicFields, client: LLMClient
) -> LLMResult:
    """One call per email, images included when present."""
    system, user = build_prompt(parsed, det)
    return client.classify(system, user, parsed.images)


# --- Anthropic adapter -------------------------------------------------------------

DEFAULT_MODEL = "claude-opus-5-5"
DEFAULT_EFFORT = "medium"
FALLBACK_BETA = "server-side-fallback-2026-07-01"

_MAGIC: list[tuple[bytes, str]] = [
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
]


def sniff_media_type(data: bytes) -> str | None:
    """Image type from the file's bytes (extensions are missing or wrong in the wild)."""
    for magic, media in _MAGIC:
        if data.startswith(magic):
            return media
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def llm_json_schema() -> dict:
    """LLMResult's schema in the strict form structured outputs expect."""

    def strip(node):
        if isinstance(node, dict):
            if isinstance(node.get("title"), str):
                node.pop("title")  # a display annotation, not the "title" field
            for key, value in node.items():
                if key == "properties":
                    for prop in value.values():
                        strip(prop)
                else:
                    strip(value)
        elif isinstance(node, list):
            for value in node:
                strip(value)
        return node

    schema = strip(LLMResult.model_json_schema())
    schema["additionalProperties"] = False
    schema["required"] = list(schema["properties"])
    return schema


def image_content(images: list[InlineImage]) -> tuple[list[dict], list[str]]:
    """Content blocks for the images, each labelled to match the prompt's image list.

    Formats the API can't take are described in text instead and reported as warnings.
    """
    import base64

    blocks: list[dict] = []
    warnings: list[str] = []
    for i, img in enumerate(images, 1):
        data = img.path.read_bytes()
        media = sniff_media_type(data)
        if media is None:
            blocks.append({"type": "text", "text": f"Image {i} ({img.path.name}): not attached, unsupported format."})
            warnings.append(f"{img.path.name}: unsupported image format, not sent")
            continue
        blocks.append({"type": "text", "text": f"Image {i} ({img.path.name}):"})
        blocks.append({
            "type": "image",
            "source": {"type": "base64", "media_type": media,
                       "data": base64.standard_b64encode(data).decode("ascii")},
        })
    return blocks, warnings


class AnthropicLLMClient:
    """Claude via the Anthropic SDK: image input + structured output (JSON schema).

    Sampling parameters (temperature) are no longer accepted by the API, so run-to-run
    stability comes from the fixed prompt, the constrained schema and the cache.
    Server-side refusal fallback is on, so a policy decline is retried on a fallback
    model inside the same call.
    """

    def __init__(self, model: str = DEFAULT_MODEL, effort: str = DEFAULT_EFFORT,
                 max_tokens: int = 16000, sdk_client=None):
        if sdk_client is None:
            import anthropic

            sdk_client = anthropic.Anthropic(max_retries=4)
        self.sdk = sdk_client
        self.model = model
        self.effort = effort
        self.max_tokens = max_tokens
        self.model_id = f"anthropic/{model}/effort={effort}"
        self.last_warnings: list[str] = []
        self._schema = llm_json_schema()

    def classify(self, system: str, user: str, images: list[InlineImage]) -> LLMResult:
        blocks, self.last_warnings = image_content(images)
        response = self.sdk.beta.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": [*blocks, {"type": "text", "text": user}]}],
            output_config={
                "effort": self.effort,
                "format": {"type": "json_schema", "schema": self._schema},
            },
            betas=[FALLBACK_BETA],
            fallbacks="default",
        )
        if response.stop_reason == "refusal":
            details = getattr(response, "stop_details", None)
            raise LLMResponseError(f"model declined: {getattr(details, 'category', None)}")
        if response.stop_reason == "max_tokens":
            raise LLMResponseError("response cut off at max_tokens")
        text = next((b.text for b in response.content if b.type == "text"), None)
        if text is None:
            raise LLMResponseError("response has no text block")
        return parse_llm_response(text)
