"""FactTightenNode — Stage B of script generation.

Takes the draft script and rewrites it with hidden trace tags per paragraph:
  [Beat Bxx | Claims Cxxx,Cyyy]

Also runs post-script validators (entity provenance, word count, essay blocks,
rehook cadence) and logs any issues.
"""

from __future__ import annotations

import json
from typing import Any

from history_tales_agent.prompts.templates import FACT_TIGHTEN_SYSTEM, FACT_TIGHTEN_USER
from history_tales_agent.state import Claim, TimelineBeat
from history_tales_agent.utils.llm import call_llm
from history_tales_agent.utils.logging import get_logger
from history_tales_agent.validators import (
    run_post_script_validation,
    strip_trace_tags,
)

logger = get_logger(__name__)


def fact_tighten_node(state: dict[str, Any]) -> dict[str, Any]:
    """Fact-tighten the draft script and add trace tags."""
    logger.info("node_start", node="FactTightenNode")

    draft_script = state.get("draft_script", "") or state.get("final_script", "")
    claims: list[Claim] = state.get("claims", [])
    beats: list[TimelineBeat] = state.get("timeline_beats", [])
    target_words = state.get("target_words", 1860)
    min_words = state.get("min_words", 1674)
    max_words = state.get("max_words", 2046)
    rehook_interval = state.get("rehook_interval", (60, 90))

    if not draft_script:
        return {
            "errors": state.get("errors", []) + ["FactTightenNode: No draft script"],
            "current_node": "FactTightenNode",
        }

    # Build timeline beats JSON with beat IDs
    timeline_json = json.dumps(
        [
            {
                "beat_id": f"B{i + 1:02d}",
                "timestamp": b.timestamp,
                "event": b.event,
                "pov": b.pov,
                "tension": b.tension_level,
            }
            for i, b in enumerate(beats)
        ],
        indent=2,
    )

    # Build claims with IDs and script_language
    claims_with_ids = json.dumps(
        [
            {
                "claim_id": c.claim_id,
                "claim_text": c.claim_text,
                "confidence": c.confidence,
                "script_language": c.script_language,
            }
            for c in claims
            if c.confidence in ("High", "Moderate")
        ][:30],
        indent=2,
    )

    draft_word_count = len(draft_script.split())

    user_prompt = FACT_TIGHTEN_USER.format(
        target_words=target_words,
        min_words=min_words,
        max_words=max_words,
        draft_script=draft_script,
        draft_word_count=draft_word_count,
        timeline_beats_json=timeline_json,
        claims_with_ids=claims_with_ids,
    )

    try:
        tightened = call_llm(FACT_TIGHTEN_SYSTEM, user_prompt, temperature=0.5, tier="fast")
    except Exception as e:
        logger.error("fact_tighten_failed", error=str(e))
        # Fall back to the draft
        return {
            "final_script": draft_script,
            "current_node": "FactTightenNode",
        }

    # Strip trace tags for the final script (but keep the tagged version for audit)
    final_script = strip_trace_tags(tightened)
    word_count = len(final_script.split())

    # ── Word-count floor: if the LLM destroyed the script, fall back ──
    # Allow up to 15% shrinkage; anything more means the model summarised.
    floor = int(draft_word_count * 0.85)
    if word_count < floor:
        loss_pct = round((1 - word_count / draft_word_count) * 100, 1)
        logger.error(
            "fact_tighten_word_loss",
            draft_words=draft_word_count,
            result_words=word_count,
            loss_pct=loss_pct,
            action="falling_back_to_draft",
        )
        final_script = draft_script
        word_count = draft_word_count

    logger.info("fact_tighten_complete", word_count=word_count, tagged_len=len(tightened))

    # ── Run post-script validators ──
    avg_rehook = (rehook_interval[0] + rehook_interval[1]) // 2
    wpm = state.get("words_per_minute", 155)
    rehook_words = int(avg_rehook * (wpm / 60))

    claims_dicts = [
        {"claim_id": c.claim_id, "claim_text": c.claim_text, "named_entities": c.named_entities}
        for c in claims
    ]
    beats_dicts = [
        {"event": b.event, "pov": b.pov}
        for b in beats
    ]

    report = run_post_script_validation(
        script=final_script,
        verified_claims=claims_dicts,
        timeline_beats=beats_dicts,
        min_words=min_words,
        max_words=max_words,
        rehook_words=rehook_words,
    )

    validation_issues: list[str] = []
    for issue in report.issues:
        msg = f"[{issue.severity.upper()}] {issue.code}: {issue.message}"
        validation_issues.append(msg)
        log_fn = logger.error if issue.severity == "hard" else logger.warning
        log_fn("post_script_issue", code=issue.code, message=issue.message)

    return {
        "final_script": final_script,
        "validation_issues": state.get("validation_issues", []) + validation_issues,
        "current_node": "FactTightenNode",
    }
