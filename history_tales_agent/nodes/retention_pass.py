"""RetentionPassNode — surgery-only retention improvement pass.

SURGERY-ONLY: may NOT introduce new named entities or new events.
Only rewrites/reordering using existing beats/claims. Must maintain word
count within min/max.
"""

from __future__ import annotations

from typing import Any

from history_tales_agent.prompts.templates import (
    RETENTION_PASS_SYSTEM,
    RETENTION_PASS_USER,
)
from history_tales_agent.utils.llm import call_llm
from history_tales_agent.utils.feedback_memory import load_lessons_prompt
from history_tales_agent.utils.logging import get_logger
from history_tales_agent.validators import validate_retention_no_new_entities

logger = get_logger(__name__)


def retention_pass_node(state: dict[str, Any]) -> dict[str, Any]:
    """Run retention analysis and improvement pass on the script."""
    logger.info("node_start", node="RetentionPassNode")

    script = state.get("final_script", "")
    rehook_interval = state.get("rehook_interval", (60, 90))
    target_words = state.get("target_words", 1860)
    min_words = state.get("min_words", 1674)
    max_words = state.get("max_words", 2046)

    if not script:
        return {
            "errors": state.get("errors", []) + ["RetentionPassNode: No script"],
            "current_node": "RetentionPassNode",
        }

    current_word_count = len(script.split())
    avg_rehook = (rehook_interval[0] + rehook_interval[1]) // 2
    wpm = state.get("words_per_minute", 155)
    rehook_words = int(avg_rehook * (wpm / 60))

    user_prompt = RETENTION_PASS_USER.format(
        rehook_interval=f"{rehook_interval[0]}–{rehook_interval[1]}",
        rehook_words=rehook_words,
        target_words=target_words,
        min_words=min_words,
        max_words=max_words,
        current_word_count=current_word_count,
        script=script,
    )

    # ── Inject lessons from previous runs ──
    lessons = load_lessons_prompt()
    if lessons:
        user_prompt = lessons + "\n\n" + user_prompt
        logger.info("lessons_injected", node="RetentionPassNode", lessons_len=len(lessons))

    try:
        revised = call_llm(RETENTION_PASS_SYSTEM, user_prompt, temperature=0.6, tier="fast")
    except Exception as e:
        logger.error("retention_pass_failed", error=str(e))
        return {"current_node": "RetentionPassNode"}

    # Split out retention notes if present
    if "RETENTION NOTES:" in revised:
        parts = revised.split("RETENTION NOTES:", 1)
        revised_script = parts[0].strip()
        retention_notes = parts[1].strip()
        logger.info("retention_notes", notes=retention_notes[:200])
    else:
        revised_script = revised.strip()

    word_count = len(revised_script.split())
    input_word_count = len(script.split())

    # Guard: if retention pass blew past max_words, fall back to original
    if word_count > max_words and input_word_count <= max_words:
        logger.warning(
            "retention_pass_over_limit",
            input_wc=input_word_count,
            output_wc=word_count,
            max_words=max_words,
            msg="Retention pass exceeded max_words — using original script",
        )
        revised_script = script
        word_count = input_word_count

    # Guard: if retention pass dropped below min_words, fall back to original
    if word_count < min_words and input_word_count >= min_words:
        logger.warning(
            "retention_pass_under_limit",
            input_wc=input_word_count,
            output_wc=word_count,
            min_words=min_words,
            msg="Retention pass went below min_words — using original script",
        )
        revised_script = script
        word_count = input_word_count

    # Guard: bounded reduction — retention pass must not cut >15% (Change 25)
    if input_word_count > 0:
        reduction_pct = (1 - word_count / input_word_count) * 100
        if reduction_pct > 15:
            logger.warning(
                "retention_pass_overcut",
                input_wc=input_word_count,
                output_wc=word_count,
                reduction_pct=round(reduction_pct, 1),
                msg="Retention pass cut too much (>15%) — using original script",
            )
            revised_script = script
            word_count = input_word_count

    # Guard: paragraph count — retention pass must not destroy structure
    input_paragraphs = len([p for p in script.split("\n\n") if p.strip()])
    output_paragraphs = len([p for p in revised_script.split("\n\n") if p.strip()])
    if input_paragraphs > 0 and output_paragraphs < input_paragraphs * 0.7:
        logger.warning(
            "retention_pass_paragraph_loss",
            input_paras=input_paragraphs,
            output_paras=output_paragraphs,
            msg="Retention pass lost too many paragraphs (>30%) — using original script",
        )
        revised_script = script
        word_count = input_word_count

    # Guard: surgery-only — no new named entities allowed
    entity_issues = validate_retention_no_new_entities(script, revised_script)
    if entity_issues:
        for issue in entity_issues:
            logger.warning("retention_new_entity", name=issue.message)
        logger.warning(
            "retention_pass_new_entities",
            count=len(entity_issues),
            msg="Retention pass introduced new entities — using original script",
        )
        revised_script = script
        word_count = input_word_count

    logger.info("retention_pass_complete", word_count=word_count)

    return {
        "final_script": revised_script,
        "current_node": "RetentionPassNode",
    }
