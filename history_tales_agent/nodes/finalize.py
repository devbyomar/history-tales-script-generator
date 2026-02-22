"""FinalizeNode — packages everything into the final output."""

from __future__ import annotations

from typing import Any

from history_tales_agent.state import QCReport
from history_tales_agent.utils.feedback_memory import save_run_feedback
from history_tales_agent.utils.logging import get_logger

logger = get_logger(__name__)


def finalize_node(state: dict[str, Any]) -> dict[str, Any]:
    """Package the final output with all artifacts."""
    logger.info("node_start", node="FinalizeNode")

    script = state.get("final_script", "")
    qc_report: QCReport | None = state.get("qc_report")

    if not script:
        logger.error("finalize_no_script")
        return {"current_node": "FinalizeNode"}

    # Log final summary
    word_count = len(script.split())
    logger.info(
        "pipeline_complete",
        word_count=word_count,
        qc_pass=qc_report.overall_pass if qc_report else False,
        emotional_score=state.get("emotional_intensity_score", 0),
        sensory_score=state.get("sensory_density_score", 0),
        source_count=len(state.get("sources_log", [])),
        claims_count=len(state.get("claims", [])),
        format=state.get("format_tag", ""),
    )

    # ── Save feedback to memory for future runs ──
    chosen = state.get("chosen_topic")
    try:
        save_run_feedback(
            topic_title=chosen.title if chosen else "Unknown",
            era=chosen.era if chosen else state.get("era_focus", ""),
            geo=chosen.geo if chosen else state.get("geo_focus", ""),
            word_count=word_count,
            target_words=state.get("target_words", 0),
            qc_pass=qc_report.overall_pass if qc_report else False,
            issues=qc_report.issues if qc_report else [],
            recommendations=qc_report.recommendations if qc_report else [],
            emotional_score=state.get("emotional_intensity_score", 0.0),
            sensory_score=state.get("sensory_density_score", 0.0),
            iteration_count=state.get("iteration_count", 0),
        )
    except Exception as e:
        logger.warning("feedback_save_failed", error=str(e))

    return {"current_node": "FinalizeNode"}
