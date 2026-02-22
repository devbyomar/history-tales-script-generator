"""Output formatter — writes final artifacts to disk."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from history_tales_agent.state import AgentState, Claim, QCReport, SourceEntry
from history_tales_agent.utils.logging import get_logger

logger = get_logger(__name__)


def format_output(state: dict[str, Any], output_dir: str = "output") -> Path:
    """Write all output artifacts to disk.

    Creates:
        output/script.md
        output/sources_claims_log.md
        output/qc_report.md
        output/metadata.json
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    chosen = state.get("chosen_topic")
    title = chosen.title if chosen else "Untitled"

    # --- script.md ---
    script = state.get("final_script", "")
    script_path = out / "script.md"
    script_content = f"# {title}\n\n{script}"
    script_path.write_text(script_content, encoding="utf-8")
    logger.info("wrote_script", path=str(script_path), words=len(script.split()))

    # --- sources_claims_log.md ---
    sources: list[SourceEntry] = state.get("sources_log", [])
    claims: list[Claim] = state.get("claims", [])
    log_lines = [f"# Sources & Claims Log — {title}\n"]

    log_lines.append("\n## Sources\n")
    log_lines.append("| # | Source | URL | Type | Credibility | Institutional |")
    log_lines.append("|---|--------|-----|------|-------------|---------------|")
    for i, src in enumerate(sources, 1):
        log_lines.append(
            f"| {i} | {src.name[:60]} | {src.url[:80]} | {src.source_type} | "
            f"{src.credibility_score:.2f} | {'✅' if src.is_institutional else '❌'} |"
        )

    log_lines.append("\n## Claims\n")
    log_lines.append("| # | Claim | Source | Type | Confidence | Cross-checked |")
    log_lines.append("|---|-------|--------|------|------------|---------------|")
    for i, claim in enumerate(claims, 1):
        log_lines.append(
            f"| {i} | {claim.claim_text[:80]}… | {claim.source_name[:40]} | "
            f"{claim.source_type} | {claim.confidence} | "
            f"{'✅' if claim.cross_checked else '❌'} |"
        )

    consensus = state.get("consensus_vs_contested", [])
    if consensus:
        log_lines.append("\n## Contested Points\n")
        for cc in consensus:
            log_lines.append(f"- **Claim**: {cc.get('claim', '')}")
            log_lines.append(f"  - **Conflict**: {cc.get('conflict', '')}")
            log_lines.append(f"  - **Treatment**: {cc.get('treatment', '')}\n")

    log_path = out / "sources_claims_log.md"
    log_path.write_text("\n".join(log_lines), encoding="utf-8")
    logger.info("wrote_sources_log", path=str(log_path))

    # --- qc_report.md ---
    qc: QCReport | None = state.get("qc_report")
    qc_lines = [f"# Quality Check Report — {title}\n"]
    if qc:
        qc_lines.append(f"**Overall Pass**: {'✅ PASS' if qc.overall_pass else '❌ FAIL'}\n")
        qc_lines.append(f"- Word Count: {qc.word_count} (target: {qc.target_words}, range: ±10%)")
        qc_lines.append(f"- Word Count In Range: {'✅' if qc.word_count_in_range else '❌'}")
        qc_lines.append(f"- Emotional Intensity: {qc.emotional_intensity_score:.1f}/100")
        qc_lines.append(f"- Sensory Density: {qc.sensory_density_score:.1f}/100")
        qc_lines.append(f"- Source Count: {qc.source_count}")
        qc_lines.append(f"- Institutional Source: {'✅' if qc.institutional_source_present else '❌'}")
        qc_lines.append(f"- Independent Domains: {qc.independent_domains}\n")

        if qc.issues:
            qc_lines.append("## Issues\n")
            for issue in qc.issues:
                qc_lines.append(f"- ⚠️ {issue}")

        if qc.recommendations:
            qc_lines.append("\n## Recommendations\n")
            for rec in qc.recommendations:
                qc_lines.append(f"- 💡 {rec}")
    else:
        qc_lines.append("No QC report generated.")

    qc_path = out / "qc_report.md"
    qc_path.write_text("\n".join(qc_lines), encoding="utf-8")
    logger.info("wrote_qc_report", path=str(qc_path))

    # --- metadata.json ---
    meta = {
        "title": title,
        "generated_at": datetime.now().isoformat(),
        "video_length_minutes": state.get("video_length_minutes"),
        "target_words": state.get("target_words"),
        "actual_words": len(script.split()),
        "tone": state.get("tone"),
        "format_tag": state.get("format_tag"),
        "era_focus": state.get("era_focus"),
        "geo_focus": state.get("geo_focus"),
        "emotional_intensity_score": state.get("emotional_intensity_score", 0),
        "sensory_density_score": state.get("sensory_density_score", 0),
        "source_count": len(sources),
        "claims_count": len(claims),
        "qc_pass": qc.overall_pass if qc else False,
        "chosen_topic_score": chosen.score if chosen else 0,
    }

    meta_path = out / "metadata.json"
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("wrote_metadata", path=str(meta_path))

    return out
