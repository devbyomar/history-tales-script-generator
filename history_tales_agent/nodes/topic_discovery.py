"""TopicDiscoveryNode — generates or refines topic candidates."""

from __future__ import annotations

import json
from typing import Any

from history_tales_agent.prompts.templates import (
    TOPIC_DISCOVERY_SYSTEM,
    TOPIC_DISCOVERY_USER,
)
from history_tales_agent.narrative.lenses import resolve_lenses, build_lens_prompt_block
from history_tales_agent.narrative.geo import build_geo_prompt_block
from history_tales_agent.state import AgentState, TopicCandidate
from history_tales_agent.utils.llm import call_llm_json
from history_tales_agent.utils.logging import get_logger

logger = get_logger(__name__)


def topic_discovery_node(state: dict[str, Any]) -> dict[str, Any]:
    """Generate 10 topic candidates based on input parameters.

    If topic_seed is provided, it biases discovery toward related topics.
    """
    logger.info("node_start", node="TopicDiscoveryNode")

    video_length = state.get("video_length_minutes", 12)
    era_focus = state.get("era_focus") or "any era"
    geo_focus = state.get("geo_focus") or "any region"
    topic_seed = state.get("topic_seed") or "no specific seed — discover freely"
    tone = state.get("tone", "cinematic-serious")
    sensitivity = state.get("sensitivity_level", "general audiences")

    user_prompt = TOPIC_DISCOVERY_USER.format(
        video_length_minutes=video_length,
        era_focus=era_focus,
        geo_focus=geo_focus,
        topic_seed=topic_seed,
        tone=tone,
        sensitivity_level=sensitivity,
    )

    # ── Inject narrative lens & geo context (no-ops when not set) ──
    lenses = resolve_lenses(state.get("narrative_lens"))
    lens_block = build_lens_prompt_block(lenses, state.get("lens_strength", 0.6))
    geo_block = build_geo_prompt_block(
        geo_scope=state.get("geo_scope"),
        geo_anchor=state.get("geo_anchor"),
        mobility_mode=state.get("mobility_mode"),
    )
    if lens_block:
        user_prompt += lens_block
        logger.info("lens_injected", node="TopicDiscoveryNode", lenses=[l.lens_id for l in lenses])
    if geo_block:
        user_prompt += geo_block
        logger.info("geo_injected", node="TopicDiscoveryNode")

    try:
        raw_candidates = call_llm_json(TOPIC_DISCOVERY_SYSTEM, user_prompt, tier="fast")
    except json.JSONDecodeError:
        logger.error("topic_discovery_json_parse_failed")
        return {
            "errors": state.get("errors", []) + ["TopicDiscoveryNode: JSON parse failed"],
            "current_node": "TopicDiscoveryNode",
        }

    # Parse into TopicCandidate objects
    candidates = []
    for raw in raw_candidates:
        try:
            candidate = TopicCandidate(
                title=raw.get("title", ""),
                one_sentence_hook=raw.get("one_sentence_hook", ""),
                era=raw.get("era", ""),
                geo=raw.get("geo", ""),
                core_pov=raw.get("core_pov", ""),
                timeline_window=raw.get("timeline_window", ""),
                twist_points=raw.get("twist_points", [])[:5],
                what_people_get_wrong=raw.get("what_people_get_wrong", ""),
                format_tag=raw.get("format_tag", "Countdown"),
                likely_sources=raw.get("likely_sources", []),
            )
            candidates.append(candidate)
        except Exception as e:
            logger.warning("candidate_parse_error", error=str(e))
            continue

    logger.info("topic_discovery_complete", candidates=len(candidates))

    return {
        "topic_candidates": candidates,
        "current_node": "TopicDiscoveryNode",
    }
