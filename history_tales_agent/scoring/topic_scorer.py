"""Topic scoring model with weighted scoring, hard rejects, and tie-breaking."""

from __future__ import annotations

import random
from typing import Any

from history_tales_agent.config import (
    GREENLIGHT_THRESHOLD,
    SCORING_WEIGHTS,
    YELLOW_THRESHOLD,
)
from history_tales_agent.state import TopicCandidate
from history_tales_agent.utils.logging import get_logger

logger = get_logger(__name__)


def score_topic(
    candidate: TopicCandidate,
    raw_scores: dict[str, float],
    sensitivity_level: str = "general audiences",
) -> dict[str, Any]:
    """Score a topic candidate.

    Args:
        candidate: The topic candidate to score.
        raw_scores: Dict mapping scoring dimension names to raw 0–10 scores.
        sensitivity_level: The target sensitivity level.

    Returns:
        Dict with final_score, breakdown, status, and rejection reasons.
    """
    # Normalise raw scores to weighted contributions
    breakdown: dict[str, float] = {}
    total_weight = sum(SCORING_WEIGHTS.values())

    for dimension, weight in SCORING_WEIGHTS.items():
        raw = raw_scores.get(dimension, 5.0)
        raw = max(0.0, min(10.0, raw))
        # Scale raw 0-10 to weighted contribution
        contribution = (raw / 10.0) * weight
        breakdown[dimension] = round(contribution, 2)

    raw_total = sum(breakdown.values())
    # Normalise to 0–100 scale
    normalised_score = (raw_total / total_weight) * 100

    # --- Hard rejects ---
    rejection_reasons: list[str] = []

    evidence_score = raw_scores.get("evidence_availability", 5.0)
    if evidence_score < 6:
        rejection_reasons.append(
            f"Evidence availability too low ({evidence_score}/10)"
        )

    sensitivity_score = raw_scores.get("sensitivity_fit", 5.0)
    if sensitivity_score < 6 and sensitivity_level != "mature":
        rejection_reasons.append(
            f"Sensitivity fit too low ({sensitivity_score}/10) for {sensitivity_level}"
        )

    # --- Evidence-support penalty (Change 5) ---
    # Micro-incident formats (Countdown, One Room) imply tight documentation.
    # If evidence is weak, penalise these formats because the script will
    # end up fabricating specificity the sources don't support.
    micro_incident_formats = {"Countdown", "One Room", "Impossible Choice"}
    format_tag = candidate.format_tag or ""
    if format_tag in micro_incident_formats and evidence_score < 8:
        # Penalty scales: evidence 7→2%, evidence 5→8%, evidence 3→14%
        penalty = max(0.02, (8 - evidence_score) * 0.02)
        normalised_score *= (1 - penalty)
        if evidence_score < 6:
            rejection_reasons.append(
                f"Format '{format_tag}' requires strong documented evidence "
                f"but evidence_availability is only {evidence_score}/10. "
                f"Consider a broader format like 'Chain Reaction' or 'Two Truths'."
            )

    # --- Human-POV penalty for micro-incident without strong POV ---
    human_pov = raw_scores.get("human_pov_availability", 5.0)
    if format_tag in micro_incident_formats and human_pov < 7:
        normalised_score *= 0.95  # 5% penalty
        if human_pov < 5:
            rejection_reasons.append(
                f"Format '{format_tag}' requires a well-documented named individual "
                f"but human_pov_availability is only {human_pov}/10."
            )

    # --- Runtime fit multiplier ---
    # Simulate real-time fit assessment (0.85–1.15)
    runtime_multiplier = round(random.uniform(0.92, 1.08), 3)
    final_score = round(normalised_score * runtime_multiplier, 2)

    # --- Status ---
    if rejection_reasons:
        status = "rejected"
    elif final_score >= GREENLIGHT_THRESHOLD:
        status = "greenlight"
    elif final_score >= YELLOW_THRESHOLD:
        status = "yellow"
    else:
        status = "rejected"

    result = {
        "final_score": final_score,
        "raw_score": round(normalised_score, 2),
        "breakdown": breakdown,
        "runtime_fit_multiplier": runtime_multiplier,
        "status": status,
        "rejection_reasons": rejection_reasons,
    }

    logger.info(
        "topic_scored",
        title=candidate.title,
        score=final_score,
        status=status,
    )
    return result


def rank_candidates(
    candidates: list[TopicCandidate],
    scored_results: list[dict[str, Any]],
) -> list[tuple[TopicCandidate, dict[str, Any]]]:
    """Rank candidates by score with tie-breaking rules.

    Tie-breakers (in order):
    1. Higher Human POV availability
    2. Higher Timeline Tension
    3. Higher Novelty
    """
    paired = list(zip(candidates, scored_results))

    # Filter out hard rejects
    viable = [(c, s) for c, s in paired if s["status"] != "rejected"]
    rejected = [(c, s) for c, s in paired if s["status"] == "rejected"]

    def sort_key(pair: tuple[TopicCandidate, dict[str, Any]]) -> tuple:
        _, scores = pair
        bd = scores["breakdown"]
        return (
            scores["final_score"],
            bd.get("human_pov_availability", 0),
            bd.get("timeline_tension", 0),
            bd.get("novelty_angle", 0),
        )

    viable.sort(key=sort_key, reverse=True)
    rejected.sort(key=lambda p: p[1]["final_score"], reverse=True)

    return viable + rejected


def select_best_candidate(
    ranked: list[tuple[TopicCandidate, dict[str, Any]]],
    previous_format_tag: str | None = None,
) -> TopicCandidate | None:
    """Select the best greenlit candidate, enforcing format rotation."""
    for candidate, scores in ranked:
        if scores["status"] == "rejected":
            continue

        # Format rotation: skip if matches previous
        if (
            previous_format_tag
            and candidate.format_tag == previous_format_tag
            and scores["status"] != "greenlight"
        ):
            logger.info(
                "format_rotation_skip",
                title=candidate.title,
                format=candidate.format_tag,
            )
            continue

        candidate.score = scores["final_score"]
        candidate.score_breakdown = scores["breakdown"]
        candidate.runtime_fit_multiplier = scores["runtime_fit_multiplier"]
        return candidate

    # Fallback: return best non-rejected even if format matches
    for candidate, scores in ranked:
        if scores["status"] != "rejected":
            candidate.score = scores["final_score"]
            candidate.score_breakdown = scores["breakdown"]
            candidate.runtime_fit_multiplier = scores["runtime_fit_multiplier"]
            return candidate

    return None
