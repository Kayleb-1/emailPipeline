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
