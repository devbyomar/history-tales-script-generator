"""SourceCredibilityNode — validates and scores source credibility."""

from __future__ import annotations

from typing import Any

from history_tales_agent.research.source_registry import (
    get_credibility_score,
    is_allowed_source,
    is_institutional_source,
    validate_source_diversity,
)
from history_tales_agent.state import SourceEntry
from history_tales_agent.utils.logging import get_logger

logger = get_logger(__name__)


def source_credibility_node(state: dict[str, Any]) -> dict[str, Any]:
    """Validate source credibility and ensure minimum diversity requirements."""
    logger.info("node_start", node="SourceCredibilityNode")

    sources: list[SourceEntry] = state.get("sources_log", [])
    errors = list(state.get("errors", []))

    # Score and filter sources
    validated_sources = []
    for source in sources:
        if not source.url:
            continue

        source.credibility_score = get_credibility_score(source.url)
        source.is_institutional = is_institutional_source(source.url)

        # Only keep sources with minimum credibility
        if source.credibility_score >= 0.3:
            validated_sources.append(source)
        else:
            logger.warning("low_credibility_source", url=source.url, score=source.credibility_score)

    # Check diversity
    diversity = validate_source_diversity(
        [{"url": s.url} for s in validated_sources]
    )

    if not diversity["meets_minimum"]:
        errors.append(
            f"Source diversity insufficient: only {diversity['unique_domains']} "
            f"unique domains (need ≥3). Domains: {diversity['domains']}"
        )

    if not diversity["has_institutional"]:
        errors.append("No institutional source (.edu, .gov, archive, museum) found")

    logger.info(
        "credibility_check_complete",
        total=len(validated_sources),
        unique_domains=diversity["unique_domains"],
        has_institutional=diversity["has_institutional"],
    )

    return {
        "sources_log": validated_sources,
        "errors": errors,
        "current_node": "SourceCredibilityNode",
    }
