"""CrossCheckNode — cross-references claims across sources."""

from __future__ import annotations

import json
from typing import Any

from history_tales_agent.prompts.templates import CROSS_CHECK_SYSTEM, CROSS_CHECK_USER
from history_tales_agent.state import Claim
from history_tales_agent.utils.llm import call_llm_json
from history_tales_agent.utils.logging import get_logger

logger = get_logger(__name__)


def cross_check_node(state: dict[str, Any]) -> dict[str, Any]:
    """Cross-check claims against the research corpus."""
    logger.info("node_start", node="CrossCheckNode")

    claims: list[Claim] = state.get("claims", [])
    corpus = state.get("research_corpus", [])

    if not claims:
        return {
            "errors": state.get("errors", []) + ["CrossCheckNode: No claims to check"],
            "current_node": "CrossCheckNode",
        }

    # Build corpus summary
    corpus_summary = "\n\n".join(
        f"[{item.get('source', 'Unknown')}] {item.get('title', '')}: "
        f"{item.get('text', '')[:2000]}"
        for item in corpus[:10]
    )

    # Batch claims for cross-checking
    claims_json = json.dumps(
        [{"claim_text": c.claim_text, "source": c.source_name, "confidence": c.confidence}
         for c in claims[:30]],  # Cap at 30 for context window
        indent=2,
    )

    try:
        user_prompt = CROSS_CHECK_USER.format(
            claims_json=claims_json,
            corpus_summary=corpus_summary[:8000],
        )
        checked = call_llm_json(CROSS_CHECK_SYSTEM, user_prompt)
    except Exception as e:
        logger.error("cross_check_failed", error=str(e))
        return {"current_node": "CrossCheckNode"}

    # Update claims with cross-check results
    checked_map = {c.get("claim_text", "")[:80]: c for c in checked}
    consensus_contested = []

    for claim in claims:
        key = claim.claim_text[:80]
        if key in checked_map:
            cc = checked_map[key]
            claim.cross_checked = True
            claim.confidence = cc.get("confidence_after_check", claim.confidence)
            claim.cross_check_notes = cc.get("conflicting_info", "")

            if cc.get("conflicting_info"):
                consensus_contested.append({
                    "claim": claim.claim_text,
                    "conflict": cc["conflicting_info"],
                    "treatment": cc.get("recommended_treatment", "Note disagreement"),
                })

    logger.info(
        "cross_check_complete",
        checked=len(checked),
        contested=len(consensus_contested),
    )

    return {
        "claims": claims,
        "consensus_vs_contested": consensus_contested,
        "current_node": "CrossCheckNode",
    }
