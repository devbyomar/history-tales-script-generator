"""EmotionalIntensityMeterNode — scores emotional intensity of the script."""

from __future__ import annotations

from typing import Any

from history_tales_agent.prompts.templates import (
    EMOTIONAL_INTENSITY_SYSTEM,
    EMOTIONAL_INTENSITY_USER,
)
from history_tales_agent.utils.llm import call_llm_json
from history_tales_agent.utils.logging import get_logger

logger = get_logger(__name__)


def emotional_intensity_node(state: dict[str, Any]) -> dict[str, Any]:
    """Measure the emotional intensity of the script."""
    logger.info("node_start", node="EmotionalIntensityMeterNode")

    script = state.get("final_script", "")
    if not script:
        return {"current_node": "EmotionalIntensityMeterNode"}

    user_prompt = EMOTIONAL_INTENSITY_USER.format(script=script[:60000])

    try:
        result = call_llm_json(EMOTIONAL_INTENSITY_SYSTEM, user_prompt, tier="fast")
    except Exception as e:
        logger.error("emotional_intensity_failed", error=str(e))
        return {
            "emotional_intensity_score": 0.0,
            "current_node": "EmotionalIntensityMeterNode",
        }

    score = result.get("score", 0)
    weak_sections = result.get("weak_sections", [])
    recommendations = result.get("recommendations", [])

    if score < 70:
        logger.warning(
            "emotional_intensity_low",
            score=score,
            weak_sections=weak_sections,
            msg="Below threshold — escalation rewrite recommended",
        )

    logger.info("emotional_intensity_complete", score=score)

    return {
        "emotional_intensity_score": float(score),
        "current_node": "EmotionalIntensityMeterNode",
    }
