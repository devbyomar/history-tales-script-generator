"""TimelineBuilderNode — arranges claims into a dramatic timeline."""

from __future__ import annotations

import json
from typing import Any

from history_tales_agent.prompts.templates import (
    TIMELINE_BUILDER_SYSTEM,
    TIMELINE_BUILDER_USER,
)
from history_tales_agent.narrative.lenses import resolve_lenses, build_lens_prompt_block
from history_tales_agent.narrative.geo import build_geo_prompt_block
from history_tales_agent.state import Claim, TimelineBeat, TopicCandidate
from history_tales_agent.utils.llm import call_llm_json
from history_tales_agent.utils.logging import get_logger
from history_tales_agent.validators import (
    validate_tension_escalation,
    validate_twist_distribution,
)

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
    if geo_block:
        user_prompt += geo_block

    try:
        raw_beats = call_llm_json(TIMELINE_BUILDER_SYSTEM, user_prompt, tier="fast")
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

    # ── EMPTY TIMELINE FALLBACK (Change 7) ────────────────────────────
    # If the LLM returned zero beats or zero twists, that means the
    # evidence base was too weak to construct a real timeline.
    # Retry ONCE using only verified claims as anchors.
    twist_count = sum(1 for b in beats if b.is_twist)
    if len(beats) == 0 or twist_count == 0:
        logger.warning(
            "timeline_empty_or_twistless",
            beats=len(beats),
            twists=twist_count,
            action="retrying_from_claims_only",
        )
        # Build a simplified user prompt focused purely on claims
        fallback_prompt = (
            f"Build a dramatic timeline for a {video_length}-minute YouTube history video.\n\n"
            f"Topic: {chosen.title}\nCore POV: {chosen.core_pov}\n"
            f"Timeline Window: {chosen.timeline_window}\nFormat: {chosen.format_tag}\n\n"
            f"IMPORTANT: The previous attempt produced zero usable beats.\n"
            f"Build the timeline STRICTLY from these verified claims — do NOT\n"
            f"invent events. If only pattern-level evidence exists, frame beats\n"
            f"as representative moments within documented patterns.\n\n"
            f"Verified claims:\n{verified_claims}\n\n"
            f"Create a sequence of timeline beats with at least {max(4, rehook_count // 2)} beats "
            f"and at least 2 twist points.\n\n"
            f"For each beat provide: timestamp, event, pov, tension_level (1-10), "
            f"is_twist (boolean), open_loop, resolves_loop.\n\n"
            f"Return a JSON array. Return ONLY the JSON array."
        )
        try:
            raw_beats_retry = call_llm_json(TIMELINE_BUILDER_SYSTEM, fallback_prompt, tier="fast")
            retry_beats = []
            for rb in raw_beats_retry:
                beat = TimelineBeat(
                    timestamp=rb.get("timestamp", ""),
                    event=rb.get("event", ""),
                    pov=rb.get("pov", ""),
                    tension_level=rb.get("tension_level", 5),
                    is_twist=rb.get("is_twist", False),
                    open_loop=rb.get("open_loop", ""),
                    resolves_loop=rb.get("resolves_loop", ""),
                )
                retry_beats.append(beat)

            retry_twists = sum(1 for b in retry_beats if b.is_twist)
            if len(retry_beats) > len(beats):
                beats = retry_beats
                logger.info("timeline_retry_success", beats=len(beats), twists=retry_twists)
            else:
                logger.warning("timeline_retry_still_empty", beats=len(retry_beats))
        except Exception as e:
            logger.error("timeline_retry_failed", error=str(e))

    # Final safety: if still zero beats, inject a structural warning
    if len(beats) == 0:
        logger.error("timeline_structurally_empty", action="injecting_warning")

    logger.info("timeline_built", beats=len(beats), twists=sum(1 for b in beats if b.is_twist))

    # ── Deterministic tension & twist validation ──
    beats_dicts = [
        {"tension_level": b.tension_level, "is_twist": b.is_twist} for b in beats
    ]
    tension_issues = validate_tension_escalation(beats_dicts)
    twist_issues = validate_twist_distribution(beats_dicts)
    validation_warnings = []
    for issue in tension_issues + twist_issues:
        validation_warnings.append(f"[{issue.code}] {issue.message}")
        logger.warning("timeline_validation", code=issue.code, message=issue.message)

    return {
        "timeline_beats": beats,
        "validation_issues": state.get("validation_issues", []) + validation_warnings,
        "current_node": "TimelineBuilderNode",
    }
