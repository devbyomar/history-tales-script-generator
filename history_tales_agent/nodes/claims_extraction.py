"""ClaimsExtractionNode — extracts verifiable claims from research corpus."""

from __future__ import annotations

import json
from typing import Any

from history_tales_agent.prompts.templates import (
    CLAIMS_EXTRACTION_SYSTEM,
    CLAIMS_EXTRACTION_USER,
)
from history_tales_agent.state import Claim, TopicCandidate
from history_tales_agent.utils.llm import call_llm_json
from history_tales_agent.utils.logging import get_logger

logger = get_logger(__name__)


def claims_extraction_node(state: dict[str, Any]) -> dict[str, Any]:
    """Extract factual claims from the research corpus."""
    logger.info("node_start", node="ClaimsExtractionNode")

    chosen: TopicCandidate | None = state.get("chosen_topic")
    corpus = state.get("research_corpus", [])

    if not chosen or not corpus:
        return {
            "errors": state.get("errors", []) + ["ClaimsExtractionNode: Missing topic or corpus"],
            "current_node": "ClaimsExtractionNode",
        }

    all_claims: list[Claim] = []

    # Cap at 5 best sources to avoid excessive LLM calls
    filtered_corpus = [item for item in corpus if item.get("text", "") and len(item.get("text", "")) >= 100]
    filtered_corpus = filtered_corpus[:5]

    logger.info("claims_extraction_sources", total_corpus=len(corpus), using=len(filtered_corpus))

    # Global claim counter for sequential IDs
    claim_counter = 1

    for item in filtered_corpus:
        text = item.get("text", "")

        try:
            # Pass the starting claim ID so IDs are globally unique
            claim_id_start = f"C{claim_counter:03d}"
            user_prompt = CLAIMS_EXTRACTION_USER.format(
                topic_title=chosen.title,
                research_text=text[:6000],
                source_name=item.get("source", "Unknown"),
                source_url=item.get("url", ""),
                claim_id_start=claim_id_start,
            )

            raw_claims = call_llm_json(CLAIMS_EXTRACTION_SYSTEM, user_prompt, tier="fast")

            for rc in raw_claims:
                claim = Claim(
                    claim_id=rc.get("claim_id", f"C{claim_counter:03d}"),
                    claim_text=rc.get("claim_text", ""),
                    source_name=item.get("source", "Unknown"),
                    source_url=item.get("url", ""),
                    source_type=rc.get("source_type", "Secondary"),
                    confidence=rc.get("confidence", "Moderate"),
                    cross_checked=False,
                    date_anchor=rc.get("date_anchor", ""),
                    named_entities=rc.get("named_entities", []),
                    quote_candidate=rc.get("quote_candidate", False),
                )
                all_claims.append(claim)
                claim_counter += 1

        except Exception as e:
            logger.warning("claims_extraction_error", source=item.get("title"), error=str(e))

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
