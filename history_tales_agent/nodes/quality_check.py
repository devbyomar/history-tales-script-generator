"""QualityCheckNode — final quality control pass."""

from __future__ import annotations

import json
from typing import Any

from history_tales_agent.prompts.templates import QC_SYSTEM, QC_USER
from history_tales_agent.research.source_registry import validate_source_diversity
from history_tales_agent.state import Claim, QCReport, SourceEntry
from history_tales_agent.utils.llm import call_llm_json
from history_tales_agent.utils.logging import get_logger

logger = get_logger(__name__)


def quality_check_node(state: dict[str, Any]) -> dict[str, Any]:
    """Run final quality checks on the complete script."""
    logger.info("node_start", node="QualityCheckNode")

    script = state.get("final_script", "")
    target_words = state.get("target_words", 1860)
    min_words = state.get("min_words", 1674)
    max_words = state.get("max_words", 2046)
    emotional_score = state.get("emotional_intensity_score", 0)
    sensory_score = state.get("sensory_density_score", 0)
    sources: list[SourceEntry] = state.get("sources_log", [])
    claims: list[Claim] = state.get("claims", [])

    if not script:
        return {
            "qc_report": QCReport(overall_pass=False, issues=["No script generated"]),
            "current_node": "QualityCheckNode",
        }

    word_count = len(script.split())

    # Source diversity check
    diversity = validate_source_diversity([{"url": s.url} for s in sources])
    institutional_present = any(s.is_institutional for s in sources)

    claims_summary = "\n".join(
        f"- [{c.confidence}] {c.claim_text[:100]}... (cross-checked: {c.cross_checked})"
        for c in claims[:20]
    )

    user_prompt = QC_USER.format(
        script=script[:12000],
        word_count=word_count,
        target_words=target_words,
        min_words=min_words,
        max_words=max_words,
        emotional_intensity_score=emotional_score,
        sensory_density_score=sensory_score,
        source_count=len(sources),
        institutional_sources=institutional_present,
        independent_domains=diversity["unique_domains"],
        claims_summary=claims_summary,
    )

    try:
        qc_result = call_llm_json(QC_SYSTEM, user_prompt, tier="fast")
    except Exception as e:
        logger.error("qc_failed", error=str(e))
        qc_result = {"overall_pass": False, "issues": [f"QC error: {str(e)}"], "recommendations": []}

    # Build QC report
    issues = qc_result.get("issues", [])
    recommendations = qc_result.get("recommendations", [])

    # Programmatic checks
    word_in_range = min_words <= word_count <= max_words
    if not word_in_range:
        issues.append(f"Word count {word_count} outside range [{min_words}, {max_words}]")

    if not diversity["meets_minimum"]:
        issues.append(f"Only {diversity['unique_domains']} unique domains (need ≥3)")

    if not institutional_present:
        issues.append("No institutional source found")

    if emotional_score < 70:
        issues.append(f"Emotional intensity score {emotional_score} below 70 threshold")

    if sensory_score < 70:
        issues.append(f"Sensory density score {sensory_score} below 70 threshold")

    # Check for disclaimer
    if "historical synthesis based on cited sources" not in script.lower():
        issues.append("Missing disclaimer text")

    overall_pass = len(issues) == 0 or (
        word_in_range
        and emotional_score >= 60
        and sensory_score >= 60
    )

    report = QCReport(
        overall_pass=overall_pass,
        word_count=word_count,
        target_words=target_words,
        word_count_in_range=word_in_range,
        retention_score=0.0,
        emotional_intensity_score=emotional_score,
        sensory_density_score=sensory_score,
        source_count=len(sources),
        institutional_source_present=institutional_present,
        independent_domains=diversity["unique_domains"],
        issues=issues,
        recommendations=recommendations,
    )

    logger.info(
        "qc_complete",
        overall_pass=overall_pass,
        word_count=word_count,
        issues=len(issues),
    )

    iteration_count = state.get("iteration_count", 0) + 1

    return {
        "qc_report": report,
        "current_node": "QualityCheckNode",
        "iteration_count": iteration_count,
    }
