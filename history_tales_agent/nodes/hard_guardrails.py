"""HardGuardrailsNode — deterministic validation gate before script generation.

Runs between Outline and ScriptGeneration. Enforces:
- Outline word-count sum matches target
- Open-loop resolution within 2 sections
- Tension escalation rules on timeline beats
- Twist distribution (≥50% in Act 2)

If hard issues are found, they are logged as validation_issues on the state.
The pipeline proceeds regardless (the issues are advisory at this stage since
the LLM has already produced the outline/timeline), but they are injected as
feedback into the script generation prompt.
"""

from __future__ import annotations

from typing import Any

from history_tales_agent.state import ScriptSection, TimelineBeat, Claim
from history_tales_agent.validators import run_pre_script_validation
from history_tales_agent.utils.logging import get_logger

logger = get_logger(__name__)


def hard_guardrails_node(state: dict[str, Any]) -> dict[str, Any]:
    """Run deterministic validation on outline + timeline before script gen."""
    logger.info("node_start", node="HardGuardrailsNode")

    outline: list[ScriptSection] = state.get("script_outline", [])
    beats: list[TimelineBeat] = state.get("timeline_beats", [])
    claims: list[Claim] = state.get("claims", [])
    target_words = state.get("target_words", 1860)
    rehook_interval = state.get("rehook_interval", (60, 90))

    avg_rehook = (rehook_interval[0] + rehook_interval[1]) // 2
    rehook_words = int(avg_rehook * (155 / 60))

    # Convert to dicts for validators
    outline_dicts = [
        {
            "section_name": s.section_name,
            "target_word_count": s.target_word_count,
            "open_loops": s.open_loops,
            "key_beats": s.key_beats,
            "re_hooks": s.re_hooks,
        }
        for s in outline
    ]

    beats_dicts = [
        {
            "timestamp": b.timestamp,
            "event": b.event,
            "pov": b.pov,
            "tension_level": b.tension_level,
            "is_twist": b.is_twist,
            "open_loop": b.open_loop,
            "resolves_loop": b.resolves_loop,
        }
        for b in beats
    ]

    claims_dicts = [
        {
            "claim_id": c.claim_id,
            "claim_text": c.claim_text,
            "named_entities": c.named_entities,
        }
        for c in claims
    ]

    report = run_pre_script_validation(
        outline_sections=outline_dicts,
        timeline_beats=beats_dicts,
        verified_claims=claims_dicts,
        target_words=target_words,
        rehook_words=rehook_words,
    )

    validation_issues: list[str] = []
    for issue in report.issues:
        msg = f"[{issue.severity.upper()}] {issue.code}: {issue.message}"
        validation_issues.append(msg)
        log_fn = logger.error if issue.severity == "hard" else logger.warning
        log_fn("guardrail_issue", code=issue.code, severity=issue.severity, message=issue.message)

    logger.info(
        "hard_guardrails_complete",
        passed=report.passed,
        hard_issues=len(report.hard_issues),
        soft_issues=len(report.soft_issues),
    )

    return {
        "validation_issues": state.get("validation_issues", []) + validation_issues,
        "current_node": "HardGuardrailsNode",
    }
