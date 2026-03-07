"""TopicScoringNode — scores and selects the best topic candidate.

Includes format rotation guard logic (previously a separate node).
Uses batched LLM scoring — all candidates scored in a single call.
"""

from __future__ import annotations

import json
from typing import Any

from history_tales_agent.config import (
    ALL_FORMAT_TAGS,
    WORDS_PER_MINUTE,
    WORD_TOLERANCE,
)
from history_tales_agent.prompts.templates import (
    TOPIC_SCORING_SYSTEM,
    TOPIC_SCORING_USER,
)
from history_tales_agent.scoring.topic_scorer import (
    rank_candidates,
    score_topic,
    select_best_candidate,
)
from history_tales_agent.state import TopicCandidate
from history_tales_agent.utils.llm import call_llm_json
from history_tales_agent.utils.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Format rotation guard (absorbed from the former standalone node)
# ---------------------------------------------------------------------------

def _apply_format_rotation(
    candidates: list[TopicCandidate],
    previous_format: str | None,
    requested_format: str | None,
) -> list[TopicCandidate]:
    """Enforce format rotation by adjusting format tags on candidates."""
    # If a specific format was requested, force ALL candidates to use it
    if requested_format:
        logger.info("format_forced", requested=requested_format)
        for candidate in candidates:
            candidate.format_tag = requested_format
        return candidates

    if not previous_format:
        return candidates

    # Count how many different formats we have
    formats = set(c.format_tag for c in candidates)
    logger.info(
        "format_diversity",
        unique_formats=len(formats),
        previous=previous_format,
    )

    if len(formats) <= 1 and candidates and candidates[0].format_tag == previous_format:
        # All candidates are the same format as previous — redistribute
        logger.warning("all_same_format", msg="Redistributing format tags")
        available = [f for f in ALL_FORMAT_TAGS if f != previous_format]
        for i, candidate in enumerate(candidates):
            candidate.format_tag = available[i % len(available)]

    return candidates


# ---------------------------------------------------------------------------
# Main node
# ---------------------------------------------------------------------------

def topic_scoring_node(state: dict[str, Any]) -> dict[str, Any]:
    """Apply format rotation, then batch-score all candidates in one LLM call."""
    logger.info("node_start", node="TopicScoringNode")

    candidates: list[TopicCandidate] = state.get("topic_candidates", [])
    sensitivity = state.get("sensitivity_level", "general audiences")
    video_length = state.get("video_length_minutes", 12)
    previous_format = state.get("previous_format_tag")
    requested_format = state.get("requested_format_tag")

    if not candidates:
        return {
            "errors": state.get("errors", []) + ["TopicScoringNode: No candidates to score"],
            "current_node": "TopicScoringNode",
        }

    # ── Step 1: Format rotation guard ─────────────────────────────────
    candidates = _apply_format_rotation(candidates, previous_format, requested_format)

    # ── Step 2: Build batched candidates block ────────────────────────
    candidate_blocks: list[str] = []
    for i, c in enumerate(candidates, 1):
        block = (
            f"--- Candidate {i} ---\n"
            f"Title: {c.title}\n"
            f"Hook: {c.one_sentence_hook}\n"
            f"Era: {c.era}\n"
            f"Geography: {c.geo}\n"
            f"Core POV: {c.core_pov}\n"
            f"Timeline Window: {c.timeline_window}\n"
            f"Twist Points: {', '.join(c.twist_points)}\n"
            f"What People Get Wrong: {c.what_people_get_wrong}\n"
            f"Format: {c.format_tag}\n"
            f"Likely Sources: {', '.join(c.likely_sources)}"
        )
        candidate_blocks.append(block)

    candidates_block = "\n\n".join(candidate_blocks)

    user_prompt = TOPIC_SCORING_USER.format(
        sensitivity_level=sensitivity,
        video_length_minutes=video_length,
        candidates_block=candidates_block,
    )

    # ── Step 3: Single batched LLM call ───────────────────────────────
    scored_results: list[dict[str, Any]] = []
    try:
        raw_scores_list = call_llm_json(TOPIC_SCORING_SYSTEM, user_prompt, tier="fast")

        # Ensure we got a list
        if not isinstance(raw_scores_list, list):
            raw_scores_list = [raw_scores_list]

        for i, candidate in enumerate(candidates):
            if i < len(raw_scores_list):
                result = score_topic(candidate, raw_scores_list[i], sensitivity)
            else:
                result = {
                    "final_score": 0, "raw_score": 0, "breakdown": {},
                    "runtime_fit_multiplier": 1.0, "status": "rejected",
                    "rejection_reasons": ["No score returned from batch"],
                }
            scored_results.append(result)

    except Exception as e:
        logger.warning("batch_scoring_failed", error=str(e), msg="Falling back to individual scoring")
        # Fallback: score individually (graceful degradation)
        for candidate in candidates:
            try:
                fallback_block = (
                    f"--- Candidate 1 ---\n"
                    f"Title: {candidate.title}\n"
                    f"Hook: {candidate.one_sentence_hook}\n"
                    f"Era: {candidate.era}\n"
                    f"Geography: {candidate.geo}\n"
                    f"Core POV: {candidate.core_pov}\n"
                    f"Timeline Window: {candidate.timeline_window}\n"
                    f"Twist Points: {', '.join(candidate.twist_points)}\n"
                    f"What People Get Wrong: {candidate.what_people_get_wrong}\n"
                    f"Format: {candidate.format_tag}\n"
                    f"Likely Sources: {', '.join(candidate.likely_sources)}"
                )
                fallback_prompt = TOPIC_SCORING_USER.format(
                    sensitivity_level=sensitivity,
                    video_length_minutes=video_length,
                    candidates_block=fallback_block,
                )
                raw_scores = call_llm_json(TOPIC_SCORING_SYSTEM, fallback_prompt, tier="fast")
                if isinstance(raw_scores, list):
                    raw_scores = raw_scores[0]
                result = score_topic(candidate, raw_scores, sensitivity)
                scored_results.append(result)
            except Exception as e2:
                logger.warning("scoring_error", title=candidate.title, error=str(e2))
                scored_results.append({
                    "final_score": 0, "raw_score": 0, "breakdown": {},
                    "runtime_fit_multiplier": 1.0, "status": "rejected",
                    "rejection_reasons": [f"Scoring error: {str(e2)}"],
                })

    # ── Step 4: Rank and select ───────────────────────────────────────
    ranked = rank_candidates(candidates, scored_results)
    chosen = select_best_candidate(ranked, previous_format)

    if chosen is None:
        return {
            "errors": state.get("errors", []) + ["TopicScoringNode: All candidates rejected"],
            "current_node": "TopicScoringNode",
        }

    target_words = video_length * WORDS_PER_MINUTE
    min_words = int(target_words * (1 - WORD_TOLERANCE))
    max_words = int(target_words * (1 + WORD_TOLERANCE))
    rehook_interval = (60, 90) if video_length <= 12 else (90, 120)

    logger.info("topic_selected", title=chosen.title, score=chosen.score, format=chosen.format_tag)

    return {
        "chosen_topic": chosen,
        "format_tag": chosen.format_tag,
        "target_words": target_words,
        "min_words": min_words,
        "max_words": max_words,
        "rehook_interval": rehook_interval,
        "current_node": "TopicScoringNode",
    }
