"""ScriptQualityScoresNode — scores emotional intensity AND sensory density in one call.

Replaces the former separate EmotionalIntensityMeterNode and SensoryDensityCheckNode.
"""

from __future__ import annotations

from typing import Any

from history_tales_agent.prompts.templates import (
    SCRIPT_QUALITY_SCORES_SYSTEM,
    SCRIPT_QUALITY_SCORES_USER,
)
from history_tales_agent.utils.llm import call_llm_json
from history_tales_agent.utils.logging import get_logger

logger = get_logger(__name__)


def script_quality_scores_node(state: dict[str, Any]) -> dict[str, Any]:
    """Measure emotional intensity, sensory density, and narratability in a single LLM call."""
    logger.info("node_start", node="ScriptQualityScoresNode")

    script = state.get("final_script", "")
    if not script:
        return {
            "emotional_intensity_score": 0.0,
            "sensory_density_score": 0.0,
            "narratability_score": 0.0,
            "current_node": "ScriptQualityScoresNode",
        }

    user_prompt = SCRIPT_QUALITY_SCORES_USER.format(script=script[:60000])

    try:
        result = call_llm_json(SCRIPT_QUALITY_SCORES_SYSTEM, user_prompt, tier="fast")
    except Exception as e:
        logger.error("script_quality_scores_failed", error=str(e))
        return {
            "emotional_intensity_score": 0.0,
            "sensory_density_score": 0.0,
            "narratability_score": 0.0,
            "current_node": "ScriptQualityScoresNode",
        }

    # ── Extract emotional intensity ───────────────────────────────────
    ei = result.get("emotional_intensity", {})
    ei_score = ei.get("score", 0) if isinstance(ei, dict) else 0
    if ei_score < 70:
        weak_sections = ei.get("weak_sections", []) if isinstance(ei, dict) else []
        logger.warning(
            "emotional_intensity_low",
            score=ei_score,
            weak_sections=weak_sections,
            msg="Below threshold — escalation rewrite recommended",
        )

    # ── Extract sensory density ───────────────────────────────────────
    sd = result.get("sensory_density", {})
    sd_score = sd.get("score", 0) if isinstance(sd, dict) else 0
    if sd_score < 70:
        abstract_sections = sd.get("abstract_sections", []) if isinstance(sd, dict) else []
        logger.warning(
            "sensory_density_low",
            score=sd_score,
            abstract_sections=abstract_sections,
            msg="Below threshold — Opening + Act 1 revision recommended",
        )

    # ── Extract narratability ─────────────────────────────────────────
    narr = result.get("narratability", {})
    narr_score = narr.get("score", 0) if isinstance(narr, dict) else 0
    if narr_score < 70:
        violations = narr.get("violations", []) if isinstance(narr, dict) else []
        anti_poetic_count = narr.get("anti_poetic_violation_count", 0) if isinstance(narr, dict) else 0
        closing_quality = narr.get("closing_quality", "unknown") if isinstance(narr, dict) else "unknown"
        logger.warning(
            "narratability_low",
            score=narr_score,
            anti_poetic_violations=anti_poetic_count,
            closing_quality=closing_quality,
            violations=violations[:5],
            msg="Below threshold — anti-poetic rewrite recommended",
        )

    logger.info(
        "script_quality_scores_complete",
        emotional_intensity=ei_score,
        sensory_density=sd_score,
        narratability=narr_score,
    )

    return {
        "emotional_intensity_score": float(ei_score),
        "sensory_density_score": float(sd_score),
        "narratability_score": float(narr_score),
        "current_node": "ScriptQualityScoresNode",
    }
