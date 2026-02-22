"""FinalizeNode — packages everything into the final output."""

from __future__ import annotations

from typing import Any

from history_tales_agent.state import QCReport
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

    return {"current_node": "FinalizeNode"}
