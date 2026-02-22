"""FormatRotationGuardNode — prevents repeating the same format tag."""

from __future__ import annotations

from typing import Any

from history_tales_agent.config import ALL_FORMAT_TAGS
from history_tales_agent.state import TopicCandidate
from history_tales_agent.utils.logging import get_logger

logger = get_logger(__name__)


def format_rotation_guard_node(state: dict[str, Any]) -> dict[str, Any]:
    """Enforce format rotation by penalizing candidates that match previous_format_tag.

    Does NOT remove them — just flags for the scoring node to handle.
    If all candidates share the previous format, allows the best one through.
    """
    logger.info("node_start", node="FormatRotationGuardNode")

    candidates: list[TopicCandidate] = state.get("topic_candidates", [])
    previous_format = state.get("previous_format_tag")

    if not previous_format:
        logger.info("no_previous_format", msg="No rotation enforcement needed")
        return {"current_node": "FormatRotationGuardNode"}

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

    # If there's diversity, just let scoring handle the preference
    return {
        "topic_candidates": candidates,
        "current_node": "FormatRotationGuardNode",
    }
