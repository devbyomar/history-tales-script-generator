"""OutlineNode — creates the detailed script outline."""

from __future__ import annotations

import json
from typing import Any

from history_tales_agent.prompts.templates import OUTLINE_SYSTEM, OUTLINE_USER
from history_tales_agent.narrative.lenses import resolve_lenses, build_lens_prompt_block
from history_tales_agent.narrative.geo import build_geo_prompt_block, build_planning_metadata
from history_tales_agent.state import (
    EmotionalDriver,
    RehookPlan,
    ScriptSection,
    TimelineBeat,
    TopicCandidate,
    Claim,
)
from history_tales_agent.utils.llm import call_llm_json
from history_tales_agent.utils.coerce import coerce_to_str_list
from history_tales_agent.utils.feedback_memory import load_lessons_prompt
from history_tales_agent.utils.logging import get_logger

logger = get_logger(__name__)


def outline_node(state: dict[str, Any]) -> dict[str, Any]:
    """Create a detailed script outline with word count allocations."""
    logger.info("node_start", node="OutlineNode")

    chosen: TopicCandidate | None = state.get("chosen_topic")
    beats: list[TimelineBeat] = state.get("timeline_beats", [])
    drivers: list[EmotionalDriver] = state.get("emotional_drivers", [])
    claims: list[Claim] = state.get("claims", [])
    target_words = state.get("target_words", 1860)
    tone = state.get("tone", "cinematic-serious")
    video_length = state.get("video_length_minutes", 12)

    if not chosen:
        return {
            "errors": state.get("errors", []) + ["OutlineNode: No topic"],
            "current_node": "OutlineNode",
        }

    timeline_json = json.dumps(
        [{"timestamp": b.timestamp, "event": b.event, "pov": b.pov,
          "tension": b.tension_level, "twist": b.is_twist}
         for b in beats], indent=2,
    )

    emotional_json = json.dumps(
        [{"type": d.driver_type, "description": d.description, "pov": d.pov}
         for d in drivers], indent=2,
    )

    key_claims = "\n".join(
        f"- [{c.confidence}] {c.claim_text}"
        for c in claims if c.confidence in ("High", "Moderate")
    )[:4000]

    user_prompt = OUTLINE_USER.format(
        video_length_minutes=video_length,
        target_words=target_words,
        topic_title=chosen.title,
        one_sentence_hook=chosen.one_sentence_hook,
        tone=tone,
        format_tag=chosen.format_tag,
        timeline_beats_json=timeline_json,
        emotional_drivers_json=emotional_json,
        key_claims=key_claims,
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
        logger.info("lens_injected", node="OutlineNode", lenses=[l.lens_id for l in lenses])
    if geo_block:
        user_prompt += geo_block
        logger.info("geo_injected", node="OutlineNode")

    # ── Inject lessons from previous runs ──
    lessons = load_lessons_prompt()
    if lessons:
        user_prompt = lessons + "\n\n" + user_prompt
        logger.info("lessons_injected", node="OutlineNode", lessons_len=len(lessons))

    try:
        raw_sections = call_llm_json(OUTLINE_SYSTEM, user_prompt)
    except Exception as e:
        logger.error("outline_failed", error=str(e))
        return {
            "errors": state.get("errors", []) + [f"OutlineNode: {str(e)}"],
            "current_node": "OutlineNode",
        }

    sections = []
    for rs in raw_sections:
        # Parse rehook_plan items
        rehook_plan = []
        for rp in rs.get("rehook_plan", []):
            rehook_plan.append(RehookPlan(
                approx_word_index=rp.get("approx_word_index", 0),
                purpose=rp.get("purpose", ""),
                line_stub=rp.get("line_stub", ""),
            ))

        section = ScriptSection(
            section_name=rs.get("section_name", ""),
            description=rs.get("description", ""),
            target_word_count=rs.get("target_word_count", 0),
            minute_range=rs.get("minute_range", ""),
            re_hooks=coerce_to_str_list(rs.get("re_hooks", [])),
            open_loops=coerce_to_str_list(rs.get("open_loops", [])),
            key_beats=coerce_to_str_list(rs.get("key_beats", [])),
            rehook_plan=rehook_plan,
            midpoint_shift=rs.get("midpoint_shift", ""),
            late_pressure=rs.get("late_pressure", ""),
            final_thesis=rs.get("final_thesis", ""),
        )
        sections.append(section)

    total_allocated = sum(s.target_word_count for s in sections)
    logger.info("outline_complete", sections=len(sections), total_words=total_allocated)

    return {
        "script_outline": sections,
        "current_node": "OutlineNode",
    }
