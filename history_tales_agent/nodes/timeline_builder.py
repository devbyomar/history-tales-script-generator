"""TimelineBuilderNode — arranges claims into a dramatic timeline."""

from __future__ import annotations

import json
from typing import Any

from history_tales_agent.prompts.templates import (
    TIMELINE_BUILDER_SYSTEM,
    TIMELINE_BUILDER_USER,
)
from history_tales_agent.state import Claim, TimelineBeat, TopicCandidate
from history_tales_agent.utils.llm import call_llm_json
from history_tales_agent.utils.logging import get_logger

logger = get_logger(__name__)


def timeline_builder_node(state: dict[str, Any]) -> dict[str, Any]:
    """Build a dramatic timeline from verified claims."""
    logger.info("node_start", node="TimelineBuilderNode")

    chosen: TopicCandidate | None = state.get("chosen_topic")
    claims: list[Claim] = state.get("claims", [])
    video_length = state.get("video_length_minutes", 12)
    rehook_interval = state.get("rehook_interval", (60, 90))

    if not chosen or not claims:
        return {
            "errors": state.get("errors", []) + ["TimelineBuilderNode: Missing data"],
            "current_node": "TimelineBuilderNode",
        }

    # Estimate re-hook count
    avg_interval = (rehook_interval[0] + rehook_interval[1]) / 2
    rehook_count = max(4, int((video_length * 60) / avg_interval))

    verified_claims = json.dumps(
        [{"claim": c.claim_text, "confidence": c.confidence, "source": c.source_name}
         for c in claims if c.confidence in ("High", "Moderate")][:25],
        indent=2,
    )

    user_prompt = TIMELINE_BUILDER_USER.format(
        video_length_minutes=video_length,
        topic_title=chosen.title,
        core_pov=chosen.core_pov,
        timeline_window=chosen.timeline_window,
        format_tag=chosen.format_tag,
        verified_claims=verified_claims,
        rehook_count=rehook_count,
    )

    try:
        raw_beats = call_llm_json(TIMELINE_BUILDER_SYSTEM, user_prompt)
    except Exception as e:
        logger.error("timeline_build_failed", error=str(e))
        return {
            "errors": state.get("errors", []) + [f"TimelineBuilderNode: {str(e)}"],
            "current_node": "TimelineBuilderNode",
        }

    beats = []
    for rb in raw_beats:
        beat = TimelineBeat(
            timestamp=rb.get("timestamp", ""),
            event=rb.get("event", ""),
            pov=rb.get("pov", ""),
            tension_level=rb.get("tension_level", 5),
            is_twist=rb.get("is_twist", False),
            open_loop=rb.get("open_loop", ""),
            resolves_loop=rb.get("resolves_loop", ""),
        )
        beats.append(beat)

    logger.info("timeline_built", beats=len(beats), twists=sum(1 for b in beats if b.is_twist))

    return {
        "timeline_beats": beats,
        "current_node": "TimelineBuilderNode",
    }
