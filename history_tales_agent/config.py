"""Configuration management for the History Tales agent."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Tone types
# ---------------------------------------------------------------------------
ToneType = Literal[
    "cinematic-serious",
    "investigative",
    "fast-paced",
    "somber",
    "restrained",
    "urgent",
    "claustrophobic",
    "reflective",
]

# ---------------------------------------------------------------------------
# Format tags
# ---------------------------------------------------------------------------
FormatTag = Literal[
    "Countdown",
    "One Room",
    "Two Truths",
    "Chain Reaction",
    "Impossible Choice",
    "Hunt",
]

ALL_FORMAT_TAGS: list[str] = [
    "Countdown",
    "One Room",
    "Two Truths",
    "Chain Reaction",
    "Impossible Choice",
    "Hunt",
]

# ---------------------------------------------------------------------------
# Sensitivity levels
# ---------------------------------------------------------------------------
SensitivityLevel = Literal["general audiences", "teen", "mature"]

# ---------------------------------------------------------------------------
# Word-rate constant
# ---------------------------------------------------------------------------
WORDS_PER_MINUTE = 155
WORD_TOLERANCE = 0.10  # ±10%

# ---------------------------------------------------------------------------
# Scoring weights  (sum = 100 + 6 = 106 → normalised inside scorer)
# ---------------------------------------------------------------------------
SCORING_WEIGHTS = {
    "hook_curiosity_gap": 16,
    "stakes": 16,
    "timeline_tension": 14,
    "cliffhanger_density": 10,
    "human_pov_availability": 12,
    "evidence_availability": 12,
    "novelty_angle": 10,
    "controversy_defensible": 10,
    "sensitivity_fit": 6,
}

GREENLIGHT_THRESHOLD = 78
YELLOW_THRESHOLD = 70

# ---------------------------------------------------------------------------
# Re-hook intervals (seconds)
# ---------------------------------------------------------------------------
SHORT_REHOOK_INTERVAL = (60, 90)   # 8–12 min videos
LONG_REHOOK_INTERVAL = (90, 120)   # 20–45 min videos

# ---------------------------------------------------------------------------
# Allowed source domains (partial match)
# ---------------------------------------------------------------------------
ALLOWED_SOURCE_DOMAINS: list[str] = [
    "wikipedia.org",
    "wikidata.org",
    "wikimedia.org",
    "commons.wikimedia.org",
    "archives.gov",
    "nationalarchives.gov.uk",
    "loc.gov",
    "iwm.org.uk",
    ".edu",
    ".gov",
    "doaj.org",
    "jstor.org",  # open-access subset only
    "archive.org",
    "europeana.eu",
    "bbc.co.uk/history",
    "smithsonianmag.com",
    "history.com",
]

FORBIDDEN_PATTERNS: list[str] = [
    "conspiracy",
    "truther",
    "infowars",
    "naturalnews",
    "beforeitsnews",
]


# ---------------------------------------------------------------------------
# App configuration dataclass
# ---------------------------------------------------------------------------
@dataclass
class AppConfig:
    """Central application configuration."""

    # OpenAI
    openai_api_key: str = field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY", "")
    )
    openai_model: str = field(
        default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o")
    )
    openai_temperature: float = field(
        default_factory=lambda: float(os.getenv("OPENAI_TEMPERATURE", "0.7"))
    )

    # Rate limiting
    max_requests_per_minute: int = field(
        default_factory=lambda: int(os.getenv("MAX_REQUESTS_PER_MINUTE", "20"))
    )
    max_tokens_per_minute: int = field(
        default_factory=lambda: int(os.getenv("MAX_TOKENS_PER_MINUTE", "150000"))
    )

    # Cache
    enable_cache: bool = field(
        default_factory=lambda: os.getenv("ENABLE_CACHE", "true").lower() == "true"
    )
    cache_dir: Path = field(
        default_factory=lambda: Path(os.getenv("CACHE_DIR", ".cache"))
    )

    # Logging
    log_level: str = field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO")
    )

    def validate(self) -> None:
        """Raise if critical config is missing."""
        if not self.openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY is required. Set it in .env or as an environment variable."
            )


def get_config() -> AppConfig:
    """Return a validated AppConfig instance."""
    cfg = AppConfig()
    cfg.validate()
    return cfg
