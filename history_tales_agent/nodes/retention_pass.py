"""RetentionPassNode — analyzes and improves script for viewer retention."""

from __future__ import annotations

from typing import Any

from history_tales_agent.prompts.templates import (
    RETENTION_PASS_SYSTEM,
    RETENTION_PASS_USER,
)
from history_tales_agent.utils.llm import call_llm
from history_tales_agent.utils.logging import get_logger

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

    avg_rehook = (rehook_interval[0] + rehook_interval[1]) // 2
    rehook_words = int(avg_rehook * (155 / 60))

    user_prompt = RETENTION_PASS_USER.format(
        rehook_interval=f"{rehook_interval[0]}–{rehook_interval[1]}",
        rehook_words=rehook_words,
        target_words=target_words,
        min_words=min_words,
        max_words=max_words,
        script=script,
    )

    try:
        revised = call_llm(RETENTION_PASS_SYSTEM, user_prompt, temperature=0.6)
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
    logger.info("retention_pass_complete", word_count=word_count)

    return {
        "final_script": revised_script,
        "current_node": "RetentionPassNode",
    }
