"""ClaimsExtractionNode — extracts verifiable claims from research corpus.

Uses batched LLM extraction — all source texts sent in a single call.
"""

from __future__ import annotations

import json
from typing import Any

from history_tales_agent.prompts.templates import (
    CLAIMS_EXTRACTION_SYSTEM,
    CLAIMS_EXTRACTION_USER,
)
from history_tales_agent.state import Claim, TopicCandidate
from history_tales_agent.utils.llm import call_llm_json
from history_tales_agent.utils.coerce import coerce_to_str_list
from history_tales_agent.utils.logging import get_logger

logger = get_logger(__name__)


def claims_extraction_node(state: dict[str, Any]) -> dict[str, Any]:
    """Extract factual claims from the research corpus in a single batched call."""
    logger.info("node_start", node="ClaimsExtractionNode")

    chosen: TopicCandidate | None = state.get("chosen_topic")
    corpus = state.get("research_corpus", [])

    if not chosen or not corpus:
        return {
            "errors": state.get("errors", []) + ["ClaimsExtractionNode: Missing topic or corpus"],
            "current_node": "ClaimsExtractionNode",
        }

    # Cap at 5 best sources to keep context window manageable
    filtered_corpus = [item for item in corpus if item.get("text", "") and len(item.get("text", "")) >= 100]
    filtered_corpus = filtered_corpus[:5]

    logger.info("claims_extraction_sources", total_corpus=len(corpus), using=len(filtered_corpus))

    if not filtered_corpus:
        return {
            "errors": state.get("errors", []) + ["ClaimsExtractionNode: No usable corpus items"],
            "current_node": "ClaimsExtractionNode",
        }

    # ── Build batched sources block ───────────────────────────────────
    source_blocks: list[str] = []
    for i, item in enumerate(filtered_corpus, 1):
        block = (
            f"--- Source {i}: {item.get('source', 'Unknown')} ({item.get('url', '')}) ---\n"
            f"{item.get('text', '')[:6000]}"
        )
        source_blocks.append(block)

    sources_block = "\n\n".join(source_blocks)

    user_prompt = CLAIMS_EXTRACTION_USER.format(
        topic_title=chosen.title,
        sources_block=sources_block,
    )

    # ── Single batched LLM call ───────────────────────────────────────
    all_claims: list[Claim] = []
    try:
        raw_claims = call_llm_json(CLAIMS_EXTRACTION_SYSTEM, user_prompt, tier="fast")

        # Build a quick lookup for source info fallback
        source_lookup: dict[str, dict[str, str]] = {}
        for item in filtered_corpus:
            name = item.get("source", "Unknown")
            source_lookup[name] = {
                "source": name,
                "url": item.get("url", ""),
            }

        for rc in raw_claims:
            # Try to match source from claim's source_name field
            src_name = rc.get("source_name", "Unknown")
            src_info = source_lookup.get(src_name, {"source": src_name, "url": rc.get("source_url", "")})

            claim = Claim(
                claim_id=rc.get("claim_id", f"C{len(all_claims)+1:03d}"),
                claim_text=rc.get("claim_text", ""),
                source_name=src_info["source"],
                source_url=rc.get("source_url", src_info.get("url", "")),
                source_type=rc.get("source_type", "Secondary"),
                confidence=rc.get("confidence", "Moderate"),
                cross_checked=False,
                date_anchor=rc.get("date_anchor", ""),
                named_entities=coerce_to_str_list(rc.get("named_entities", [])),
                quote_candidate=rc.get("quote_candidate", False),
            )
            all_claims.append(claim)

    except Exception as e:
        logger.error("batch_claims_extraction_failed", error=str(e))
        return {
            "errors": state.get("errors", []) + [f"ClaimsExtractionNode: {str(e)}"],
            "current_node": "ClaimsExtractionNode",
        }

    # Cap total claims to avoid bloating downstream nodes
    if len(all_claims) > 50:
        logger.info("claims_capped", original=len(all_claims), capped=50)
        # Prioritise High confidence, then Moderate, then Contested
        priority = {"High": 0, "Moderate": 1, "Contested": 2}
        all_claims.sort(key=lambda c: priority.get(c.confidence, 2))
        all_claims = all_claims[:50]

    logger.info("claims_extraction_complete", total_claims=len(all_claims))

    return {
        "claims": all_claims,
        "current_node": "ClaimsExtractionNode",
    }
