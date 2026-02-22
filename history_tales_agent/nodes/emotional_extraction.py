"""EmotionalArtifactExtractionNode — extracts doubt, miscalculation, moral tension, internal conflict."""

from __future__ import annotations

import json
from typing import Any

from history_tales_agent.prompts.templates import (
    EMOTIONAL_EXTRACTION_SYSTEM,
    EMOTIONAL_EXTRACTION_USER,
)
from history_tales_agent.state import Claim, EmotionalDriver, TopicCandidate
from history_tales_agent.utils.llm import call_llm_json
from history_tales_agent.utils.logging import get_logger

logger = get_logger(__name__)


def emotional_extraction_node(state: dict[str, Any]) -> dict[str, Any]:
    """Extract emotional artifacts: doubt, miscalculation, moral tension, internal conflict."""
    logger.info("node_start", node="EmotionalArtifactExtractionNode")

    chosen: TopicCandidate | None = state.get("chosen_topic")
    claims: list[Claim] = state.get("claims", [])
    corpus = state.get("research_corpus", [])

    if not chosen:
        return {
            "errors": state.get("errors", []) + ["EmotionalExtractionNode: No topic"],
            "current_node": "EmotionalArtifactExtractionNode",
        }

    # Build research summary
    research_summary = "\n\n".join(
        f"[{c.source_name}] {c.claim_text}" for c in claims[:20]
    )
    research_summary += "\n\n---\n\n"
    research_summary += "\n\n".join(
        f"{item.get('title', '')}: {item.get('text', '')[:1500]}"
        for item in corpus[:5]
    )

    user_prompt = EMOTIONAL_EXTRACTION_USER.format(
        topic_title=chosen.title,
        core_pov=chosen.core_pov,
        research_summary=research_summary[:8000],
    )

    try:
        raw_drivers = call_llm_json(EMOTIONAL_EXTRACTION_SYSTEM, user_prompt, tier="fast")
    except Exception as e:
        logger.error("emotional_extraction_failed", error=str(e))
        return {
            "errors": state.get("errors", []) + [f"EmotionalExtractionNode: {str(e)}"],
            "current_node": "EmotionalArtifactExtractionNode",
        }

    drivers = []
    for rd in raw_drivers:
        driver = EmotionalDriver(
            driver_type=rd.get("driver_type", "doubt"),
            description=rd.get("description", ""),
            pov=rd.get("pov", ""),
            source_reference=rd.get("source_reference", ""),
        )
        drivers.append(driver)

    # Check for missing emotional elements
    found_types = {d.driver_type for d in drivers}
    required = {"doubt", "miscalculation", "moral_tension", "internal_conflict"}
    missing = required - found_types

    if missing:
        logger.warning("emotional_gaps", missing=list(missing))

    logger.info("emotional_extraction_complete", drivers=len(drivers))

    return {
        "emotional_drivers": drivers,
        "current_node": "EmotionalArtifactExtractionNode",
    }
