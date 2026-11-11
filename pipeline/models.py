"""Types shared across the pipeline (PRD, "Types, constants and methods").

Dataclasses carry data between pipeline stages. Pydantic models sit at the two
boundaries: ``LLMResult`` (what the provider returns) and ``EmailRecord`` (what
we write to classified_emails.json).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from pipeline import taxonomy as tx

# --- pipeline stages ----------------------------------------------------------


@dataclass(frozen=True)
class EmailFolder:
    source_file: str  # folder name
    path: Path
    html_path: Path | None  # None: folder logged and skipped
    pdf_paths: list[Path] = field(default_factory=list)
    inline_dir: Path | None = None


@dataclass(frozen=True)
class InlineImage:
    path: Path
    context: str  # nearest surrounding text or caption


@dataclass
class ParsedEmail:
    folder: EmailFolder
    text: str  # HTML as text, data tables as header + pipe-delimited rows
    pdf_texts: dict[str, str] = field(default_factory=dict)  # filename -> text
    pdf_warnings: list[str] = field(default_factory=list)
    images: list[InlineImage] = field(default_factory=list)  # document order


FlagReason = Literal["unexpected_file", "unreferenced_image", "missing_image", "missing_html"]


@dataclass
class Flag:
    source_file: str
    path: str
    reason: FlagReason


@dataclass(frozen=True)
class DateCandidate:
    iso: str  # YYYY-MM-DD
    context: str  # the text around it, so the LLM can tell what it dates


@dataclass
class DeterministicFields:
    source_file: str
    pdf_attachment: list[str] | None
    folder_name: str | None  # None: LLM supplies the title
    date_candidates: list[DateCandidate] = field(default_factory=list)


# --- LLM boundary ----------------------------------------------------------------


def _enum(values: list[str]) -> dict:
    return {"enum": list(values)}


class LLMResult(BaseModel):
    """The structured-output schema sent to the provider.

    The JSON schema carries the brief's lists as enums so a provider with
    constrained decoding can only pick allowed values. Parsing stays lenient
    (plain strings): a stray value is dropped and logged by rules.py instead of
    failing the whole email.
    """

    title: str
    bank: str
    date_choice: str | None  # one of the date candidates, or None
    market_wrap: bool  # judged against the brief's definition and checklist
    primary_asset_tag: str = Field(json_schema_extra=_enum(tx.PRIMARY_ASSET_TAGS))
    asset_tags: list[str] = Field(json_schema_extra={"items": _enum(tx.ALL_ASSET_TAGS)})
    companies_mentioned: list[str]  # material companies only
    industry_subindustry: list[str] = Field(
        json_schema_extra={"items": _enum(tx.ALL_INDUSTRY_STRINGS)}
    )


# --- output record ------------------------------------------------------------------


class EmailRecord(BaseModel):
    """One entry of classified_emails.json: the brief's ten fields, nothing else.

    Validation covers allowed values and the brief's rules, so a record that
    breaks them can't be written: a failure here means a bug upstream.
    """

    model_config = ConfigDict(extra="forbid")

    folder_name: str
    bank: str
    date: str | None  # YYYY-MM-DD
    market_wrap: Literal["YES", "NO"]
    primary_asset_tag: str
    asset_tags: list[str]
    companies_mentioned: list[str]
    industry_subindustry: list[str]
    pdf_attachment: list[str] | None
    source_file: str

    @field_validator("date")
    @classmethod
    def _iso_date(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if len(v) != 10 or dt.date.fromisoformat(v).isoformat() != v:
            raise ValueError(f"date must be YYYY-MM-DD, got {v!r}")
        return v

    @field_validator("primary_asset_tag")
    @classmethod
    def _primary(cls, v: str) -> str:
        if v not in tx.PRIMARY_ASSET_TAGS:
            raise ValueError(f"{v!r} is not a primary asset class")
        return v

    @field_validator("asset_tags")
    @classmethod
    def _tags(cls, v: list[str]) -> list[str]:
        bad = [t for t in v if t not in tx.ALL_ASSET_TAGS]
        if bad:
            raise ValueError(f"unknown asset tags {bad}")
        return v

    @field_validator("industry_subindustry")
    @classmethod
    def _industries(cls, v: list[str]) -> list[str]:
        bad = [s for s in v if s not in tx.ALL_INDUSTRY_STRINGS]
        if bad:
            raise ValueError(f"unknown industry strings {bad}")
        return v

    @field_validator("pdf_attachment")
    @classmethod
    def _pdfs(cls, v: list[str] | None) -> list[str] | None:
        if v is not None and not v:
            raise ValueError("pdf_attachment is null when there are no PDFs, never []")
        return v

    @model_validator(mode="after")
    def _brief_rules(self) -> EmailRecord:
        if self.market_wrap == "YES":
            if (
                self.primary_asset_tag != tx.MARKET_WRAP
                or self.asset_tags != [tx.MARKET_WRAP]
                or self.companies_mentioned
                or self.industry_subindustry
            ):
                raise ValueError("market wrap YES requires the brief's fixed wrap fields")
            return self
        if self.primary_asset_tag not in self.asset_tags:
            raise ValueError("primary_asset_tag must be in asset_tags")
        for tag in self.asset_tags:
            parent = tx.SUB_TO_PARENT.get(tag)
            if parent and parent not in self.asset_tags:
                raise ValueError(f"sub-tag {tag!r} without its parent {parent!r}")
        if tx.EQUITY not in self.asset_tags and (
            self.companies_mentioned or self.industry_subindustry
        ):
            raise ValueError("companies and industries are Equity only")
        return self

    def to_json_dict(self) -> dict:
        """Fields in the brief's order, ready for json.dump."""
        return self.model_dump()


BRIEF_FIELD_ORDER: tuple[str, ...] = (
    "folder_name", "bank", "date", "market_wrap", "primary_asset_tag", "asset_tags",
    "companies_mentioned", "industry_subindustry", "pdf_attachment", "source_file",
)
