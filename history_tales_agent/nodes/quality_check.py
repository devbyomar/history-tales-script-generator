"""QualityCheckNode — final quality control pass."""

from __future__ import annotations

import json
from typing import Any

from history_tales_agent.prompts.templates import QC_SYSTEM, QC_USER
from history_tales_agent.research.source_registry import validate_source_diversity
from history_tales_agent.state import Claim, QCReport, SourceEntry
from history_tales_agent.utils.llm import call_llm_json
from history_tales_agent.utils.coerce import coerce_to_str_list
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
    narratability_score = state.get("narratability_score", 0)
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
        script=script[:60000],
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

    # Build QC report — normalise LLM output that may return dicts
    # instead of plain strings for issues / recommendations.
    issues = coerce_to_str_list(qc_result.get("issues", []))
    recommendations = coerce_to_str_list(qc_result.get("recommendations", []))

    # Programmatic checks
    hard_issues = []  # Block pass
    soft_issues = []  # Warn but don't block

    word_in_range = min_words <= word_count <= max_words
    if not word_in_range:
        hard_issues.append(f"Word count {word_count} outside range [{min_words}, {max_words}]")

    if not diversity["meets_minimum"]:
        soft_issues.append(f"Only {diversity['unique_domains']} unique domains (need ≥3)")

    if not institutional_present:
        soft_issues.append("No institutional source found")

    if emotional_score < 60:
        hard_issues.append(f"Emotional intensity score {emotional_score} below 60 threshold")
    elif emotional_score < 70:
        soft_issues.append(f"Emotional intensity score {emotional_score} below 70 (acceptable but could improve)")

    if sensory_score < 60:
        hard_issues.append(f"Sensory density score {sensory_score} below 60 threshold")
    elif sensory_score < 70:
        soft_issues.append(f"Sensory density score {sensory_score} below 70 (acceptable but could improve)")

    if narratability_score < 60:
        hard_issues.append(f"Narratability score {narratability_score} below 60 threshold — script has too many poetic/literary patterns for spoken narration")
    elif narratability_score < 70:
        soft_issues.append(f"Narratability score {narratability_score} below 70 — some literary patterns detected that may sound unnatural when narrated")

    # --- Historical integrity checks (Change 23 — severity tier 1) ---
    # Check timeline structural integrity
    beats = state.get("timeline_beats", [])
    if len(beats) == 0:
        hard_issues.append(
            "Timeline has zero beats — script may lack structural grounding. "
            "Evidence base may be insufficient for this topic/format combination."
        )

    # Claims-log / script topic coherence check
    if claims:
        # Check that at least some claim entities appear in the script
        claim_entities: set[str] = set()
        for c in claims:
            for ent in getattr(c, "named_entities", []) or []:
                if len(ent) > 3:
                    claim_entities.add(ent.lower())
        script_lower = script.lower()
        matched = sum(1 for e in claim_entities if e in script_lower)
        if claim_entities and matched == 0:
            hard_issues.append(
                "Claims log / script topic mismatch: zero claim entities appear "
                "in the final script. The claims may be from a different topic."
            )
        elif claim_entities and matched < len(claim_entities) * 0.15:
            soft_issues.append(
                f"Only {matched}/{len(claim_entities)} claim entities found in script. "
                f"Claims log may be partially mismatched."
            )

    # Check for disclaimer — flexible matching
    disclaimer_phrases = [
        "historical synthesis based on cited sources",
        "historical synthesis based on publicly available",
        "historical synthesis",
        "based on cited sources",
        "script is a historical",
    ]
    has_disclaimer = any(phrase in script.lower() for phrase in disclaimer_phrases)
    if not has_disclaimer:
        soft_issues.append("Missing or non-standard disclaimer text")

    # Combine LLM issues as soft (advisory)
    all_issues = hard_issues + soft_issues + issues

    # Pass if no hard issues exist
    overall_pass = len(hard_issues) == 0

    report = QCReport(
        overall_pass=overall_pass,
        word_count=word_count,
        target_words=target_words,
        word_count_in_range=word_in_range,
        retention_score=0.0,
        emotional_intensity_score=emotional_score,
        sensory_density_score=sensory_score,
        narratability_score=narratability_score,
        source_count=len(sources),
        institutional_source_present=institutional_present,
        independent_domains=diversity["unique_domains"],
        issues=all_issues,
        recommendations=recommendations,
    )

    logger.info(
        "qc_complete",
        overall_pass=overall_pass,
        word_count=word_count,
        hard_issues=len(hard_issues),
        soft_issues=len(soft_issues),
        llm_issues=len(issues),
    )

    iteration_count = state.get("iteration_count", 0) + 1

    return {
        "qc_report": report,
        "current_node": "QualityCheckNode",
        "iteration_count": iteration_count,
    }
