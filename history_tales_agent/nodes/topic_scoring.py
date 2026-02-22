"""TopicScoringNode — scores and selects the best topic candidate."""

from __future__ import annotations

import json
from typing import Any

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
from history_tales_agent.config import WORDS_PER_MINUTE, WORD_TOLERANCE

logger = get_logger(__name__)


def topic_scoring_node(state: dict[str, Any]) -> dict[str, Any]:
    """Score all topic candidates and select the best one."""
    logger.info("node_start", node="TopicScoringNode")

    candidates: list[TopicCandidate] = state.get("topic_candidates", [])
    sensitivity = state.get("sensitivity_level", "general audiences")
    video_length = state.get("video_length_minutes", 12)
    previous_format = state.get("previous_format_tag")

    if not candidates:
        return {
            "errors": state.get("errors", []) + ["TopicScoringNode: No candidates to score"],
            "current_node": "TopicScoringNode",
        }

    scored_results = []
    for candidate in candidates:
        try:
            user_prompt = TOPIC_SCORING_USER.format(
                title=candidate.title,
                one_sentence_hook=candidate.one_sentence_hook,
                era=candidate.era,
                geo=candidate.geo,
                core_pov=candidate.core_pov,
                timeline_window=candidate.timeline_window,
                twist_points=", ".join(candidate.twist_points),
                what_people_get_wrong=candidate.what_people_get_wrong,
                format_tag=candidate.format_tag,
                likely_sources=", ".join(candidate.likely_sources),
                sensitivity_level=sensitivity,
                video_length_minutes=video_length,
            )
            raw_scores = call_llm_json(TOPIC_SCORING_SYSTEM, user_prompt, tier="fast")
            result = score_topic(candidate, raw_scores, sensitivity)
            scored_results.append(result)
        except Exception as e:
            logger.warning("scoring_error", title=candidate.title, error=str(e))
            scored_results.append({
                "final_score": 0, "raw_score": 0, "breakdown": {},
                "runtime_fit_multiplier": 1.0, "status": "rejected",
                "rejection_reasons": [f"Scoring error: {str(e)}"],
            })

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
