"""SensoryDensityCheckNode — evaluates sensory grounding of the script."""

from __future__ import annotations

from typing import Any

from history_tales_agent.prompts.templates import (
    SENSORY_DENSITY_SYSTEM,
    SENSORY_DENSITY_USER,
)
from history_tales_agent.utils.llm import call_llm_json
from history_tales_agent.utils.logging import get_logger

logger = get_logger(__name__)


def sensory_density_node(state: dict[str, Any]) -> dict[str, Any]:
    """Measure sensory density of the script."""
    logger.info("node_start", node="SensoryDensityCheckNode")

    script = state.get("final_script", "")
    if not script:
        return {"current_node": "SensoryDensityCheckNode"}

    user_prompt = SENSORY_DENSITY_USER.format(script=script[:12000])

    try:
        result = call_llm_json(SENSORY_DENSITY_SYSTEM, user_prompt, tier="fast")
    except Exception as e:
        logger.error("sensory_density_failed", error=str(e))
        return {
            "sensory_density_score": 0.0,
            "current_node": "SensoryDensityCheckNode",
        }

    score = result.get("score", 0)
    abstract_sections = result.get("abstract_sections", [])

    if score < 70:
        logger.warning(
            "sensory_density_low",
            score=score,
            abstract_sections=abstract_sections,
            msg="Below threshold — Opening + Act 1 revision recommended",
        )

    logger.info("sensory_density_complete", score=score)

    return {
        "sensory_density_score": float(score),
        "current_node": "SensoryDensityCheckNode",
    }
