"""Constants copied word for word from the brief. Never edit them to fit an email.

Asset tags: brief section 3a. Industry tags: section 3b. Market wrap checklist:
section 2 (Market Wrap Rule). Everything the LLM may return comes from here.
"""

from __future__ import annotations

# --- 3a Asset tags -----------------------------------------------------------

ASSET_TAXONOMY: dict[str, list[str]] = {
    "Macro": ["Developed Markets", "Emerging Markets"],
    "Fixed Income": ["Credit Strategy", "Rates Strategy", "Securitisation"],
    "Equity": ["Company Research", "Portfolio Strategy", "Thematic Investing"],
    "Commodities": ["Energy", "Metals", "Agriculture"],
    "FX": ["USD", "EUR", "JPY", "GBP", "CHF", "Other"],
    "Thematics": [],
    "Market Wrap": [],
}

MARKET_WRAP = "Market Wrap"
EQUITY = "Equity"

PRIMARY_ASSET_TAGS: list[str] = list(ASSET_TAXONOMY)


def _sub_to_parent(taxonomy: dict[str, list[str]]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for parent, subs in taxonomy.items():
        for sub in subs:
            if sub in mapping or sub in taxonomy:
                raise ValueError(f"asset sub-tag {sub!r} is ambiguous")
            mapping[sub] = parent
    return mapping


SUB_TO_PARENT: dict[str, str] = _sub_to_parent(ASSET_TAXONOMY)

ALL_ASSET_TAGS: list[str] = PRIMARY_ASSET_TAGS + list(SUB_TO_PARENT)

# --- 3b Industry tags --------------------------------------------------------

INDUSTRY_TAXONOMY: dict[str, list[str]] = {
    "BASIC MATERIALS": ["Agriculture", "Chemicals", "Metals & Mining", "Paper & Forest", "Steel"],
    "CONSUMER STAPLES": ["Beverages", "Consumer Products", "Food", "Retail", "Tobacco"],
    "CONSUMER CYCLICALS": [
        "Automobiles", "Branded Consumer Goods", "Business Services", "Consumer Durables",
        "Education", "Entertainment & Leisure", "Gaming", "Housing", "Lodging", "Media",
        "Restaurants & Pubs", "Retail", "Textile, Apparel & Footwear", "Travel",
    ],
    "ENERGY": ["Clean Energy", "Energy", "Gas", "Oil", "Oil Services"],
    "FINANCIAL SERVICES": [
        "Banks", "Brokers & Asset Managers", "Capital Markets", "Diversified Financials",
        "Insurance", "Real Estate", "Specialty Finance",
    ],
    "HEALTHCARE": [
        "Biotechnology", "Healthcare Services", "Life Sciences", "Medical Technology",
        "Pharmaceuticals",
    ],
    "INDUSTRIALS": [
        "Aerospace & Defense", "Capital Goods", "Construction", "Electrical Equipment",
        "Environmental Services", "Machinery", "Multi-Industry", "Packaging",
    ],
    "TECHNOLOGY": [
        "Communications Technology", "Hardware", "Info Services", "Internet", "IT Services",
        "Semiconductors", "Software", "Technology",
    ],
    "TELECOM SERVICES": [
        "Communication Services", "Satellite", "Telecom Services", "Telecom Wireless", "Towers",
    ],
    "TRANSPORTATION": [
        "Air Freight", "Airlines", "Airports", "Infrastructure", "Logistics", "Railroads",
        "Shipping", "Trucking",
    ],
    "UTILITIES": ["Diversified", "Gas", "MLPs", "Power", "Utilities", "Water"],
}

INDUSTRY_SEPARATOR = " > "
UNKNOWN_INDUSTRY = "Unknown"


def industry_string(sector: str, subindustry: str) -> str:
    """The brief's format: ``SECTOR > Subindustry``."""
    return f"{sector}{INDUSTRY_SEPARATOR}{subindustry}"


# Subindustry names repeat across sectors (Retail, Gas, Agriculture), so the
# qualified string is the only safe identifier.
ALL_INDUSTRY_STRINGS: list[str] = [
    industry_string(sector, sub)
    for sector, subs in INDUSTRY_TAXONOMY.items()
    for sub in subs
] + [UNKNOWN_INDUSTRY]

# --- 2 Market wrap checklist -------------------------------------------------

MARKET_WRAP_DEFINITION = (
    "A Market Wrap is a short daily recap of market moves — descriptive, cross-asset, "
    "multi-region, with multiple updates grouped together"
)

MARKET_WRAP_CHECKLIST: dict[str, str] = {
    "structure_multi_region": "Does the article cover multiple regions (US, Europe, Asia)?",
    "structure_geo_sections": "Does the article include multiple sections by geography?",
    "structure_markets_in_sequence": "Does the article summarise several markets in sequence?",
    "structure_short_bullets": "Does the article include short bullet-point updates across topics?",
    "assets_multiple_classes": (
        "Does the article reference multiple asset classes (equities, bonds, FX, commodities)?"
    ),
    "assets_brief_coverage": "Are different markets discussed briefly rather than in depth?",
    "timeframe_previous_session": (
        "Does the article summarise what happened in the previous trading session?"
    ),
    "timeframe_recent_moves": "Is the content focused on recent or overnight market moves?",
    "purpose_descriptive": "Is the article descriptive rather than analytical?",
    "purpose_no_forward_view": "Does the article lack a clear forward-looking investment view?",
    "title_wrap_terms": (
        "Does the title include terms like “Market Wrap”, “Morning Note”, "
        "“Daily Update”, “Market Recap”?"
    ),
    "language_summary_style": (
        "Is summary-style market language used across multiple sections of the article?"
    ),
    "language_short_statements": (
        "Are multiple asset classes described using short, descriptive statements "
        "(e.g., equities fell, yields moved, FX weakened)?"
    ),
    "language_consistently_descriptive": (
        "Is the language consistently descriptive rather than analytical throughout the article?"
    ),
    "depth_brief_topics": "Are topics covered briefly without deep explanation?",
    "depth_unrelated_updates": "Are multiple unrelated updates grouped together in one note?",
}

# Brief section 3a, "Important tagging rules", verbatim.
ASSET_TAGGING_RULES: list[str] = [
    "Only tag if the topic is materially covered, not just a passing mention",
    "Do NOT tag sub-tags (e.g. USD, JPY) unless the document has meaningful focused "
    "discussion on that specific currency",
]

# Brief section 3b, verbatim.
INDUSTRY_TAGGING_RULE = (
    "Only apply industry tags when the email has an Equity tag AND discusses specific "
    "companies or sectors."
)
UNKNOWN_INDUSTRY_RULE = "If the industry cannot be determined from the content, write: Unknown"
