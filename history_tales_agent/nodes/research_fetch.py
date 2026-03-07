"""ResearchFetchNode — gathers research from multiple credible sources.

Query discipline: searches use STABLE HISTORICAL ANCHORS only (place names,
institution names, verified people, operations, memoir titles, archival
terms).  Generated dramatic prose, rhetorical open-loops, and hypothetical
tension statements are NEVER sent as search queries.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from history_tales_agent.research.archive_client import search_all_archives
from history_tales_agent.research.wikipedia_client import (
    get_wikipedia_content,
    get_wikipedia_references,
    search_wikipedia,
)
from history_tales_agent.state import SourceEntry, TopicCandidate
from history_tales_agent.research.source_registry import (
    extract_domain,
    get_credibility_score,
    is_institutional_source,
    classify_source_type,
    validate_source_diversity,
)
from history_tales_agent.utils.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Query-discipline helpers
# ---------------------------------------------------------------------------

# Patterns that indicate generated narrative prose (not stable historical anchors)
_NARRATIVE_PROSE_SIGNALS = re.compile(
    r"(a\s+(sudden|dramatic|unexpected|critical|tense|dangerous))|"
    r"(emerges|escalates|collapses|intensifies|unfolds|reveals|exposes)|"
    r"(disagreement\s+over|tension\s+between|risk\s+of|pressure\s+to)|"
    r"(compresses|threatens|shatters|transforms|undermines)|"
    r"(what\s+if|what\s+happens|how\s+does|can\s+they|will\s+they)",
    re.IGNORECASE,
)

# Minimum word count for prose-like sentences (short entity names are fine)
_MIN_PROSE_WORDS = 6


def _is_narrative_prose(query: str) -> bool:
    """Return True if a query looks like generated dramatic prose rather than
    a stable historical anchor (place, person, institution, event name)."""
    words = query.split()
    # Short queries (≤5 words) are almost certainly entity/event names
    if len(words) <= _MIN_PROSE_WORDS:
        return False
    # Check for narrative-prose signal patterns
    return bool(_NARRATIVE_PROSE_SIGNALS.search(query))


def _extract_entity_anchors(twist_points: list[str]) -> list[str]:
    """Extract stable historical anchors from twist-point descriptions.

    Instead of sending full dramatic sentences like "A sudden schedule change
    compresses the escape timeline", extract only the noun-phrase anchors
    suitable for Wikipedia/archive search.
    """
    # Simple heuristic: extract capitalised multi-word phrases and known
    # entity patterns.  Falls back to the full string only if it's short
    # and doesn't look like narrative prose.
    anchors: list[str] = []
    # Pattern: capitalised proper nouns (2+ words) — likely names/places
    proper_noun_re = re.compile(
        r"\b([A-Z][a-z]+(?:\s+(?:de|von|van|al|el|of|the))?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b"
    )
    for twist in twist_points:
        # Try to extract proper nouns first
        matches = proper_noun_re.findall(twist)
        for m in matches:
            if len(m.split()) >= 2 and m.lower() not in {"the second", "the first", "the third"}:
                anchors.append(m)
        # If the twist is short and not prose, use it directly
        if not _is_narrative_prose(twist):
            anchors.append(twist)
    # Deduplicate while preserving order
    seen: set[str] = set()
    result: list[str] = []
    for a in anchors:
        key = a.lower().strip()
        if key not in seen:
            seen.add(key)
            result.append(a)
    return result


def _passes_relevance_filter(
    title: str,
    snippet: str,
    era: str,
    geo: str,
    core_pov: str,
    topic_title: str,
) -> bool:
    """Lightweight relevance sanity check — reject obviously off-topic results.

    Returns True if the result is plausibly related to the topic.
    We check if the result shares at least one significant token with the
    topic's era, geography, core POV, or title.
    """
    combined = f"{title} {snippet}".lower()
    # Build a set of anchor tokens from the topic metadata
    anchor_text = f"{era} {geo} {core_pov} {topic_title}".lower()
    anchor_tokens = {
        t for t in re.split(r"[\s,;:\-–—]+", anchor_text)
        if len(t) > 3  # skip short words like "the", "of", "ww2"
    }
    # Also keep important short tokens
    for short in ("ww1", "ww2", "wwi", "wwii", "pow", "cia", "kgb", "fbi", "raf", "sas"):
        if short in anchor_text:
            anchor_tokens.add(short)

    # A result passes if it shares at least one anchor token
    for token in anchor_tokens:
        if token in combined:
            return True

    # Fallback: if the result title contains any word from core_pov, accept
    pov_words = [w.lower() for w in core_pov.split() if len(w) > 2]
    for w in pov_words:
        if w in combined:
            return True

    return False


def research_fetch_node(state: dict[str, Any]) -> dict[str, Any]:
    """Fetch research from Wikipedia, archives, and institutional sources.

    Query discipline:
    - Primary queries: topic title, core POV person, era+geo context
    - Entity queries: proper nouns extracted from twist points
    - NEVER: raw dramatic prose, rhetorical questions, or speculative beats
    """
    logger.info("node_start", node="ResearchFetchNode")

    chosen: TopicCandidate | None = state.get("chosen_topic")
    if not chosen:
        return {
            "errors": state.get("errors", []) + ["ResearchFetchNode: No chosen topic"],
            "current_node": "ResearchFetchNode",
        }

    corpus: list[dict[str, Any]] = []
    sources: list[SourceEntry] = []

    # ── Build categorised search queries ──────────────────────────────
    # Category 1: Core entity queries (always stable)
    entity_queries = [chosen.core_pov]

    # Category 2: Place / institution / event queries
    place_queries = [chosen.title, f"{chosen.era} {chosen.geo}"]

    # Category 3: Extracted anchors from twist points (NOT raw prose)
    twist_anchors = _extract_entity_anchors(chosen.twist_points[:5])

    # Combine all queries, filtering out narrative prose
    all_queries: list[str] = []
    for q in entity_queries + place_queries + twist_anchors:
        q = q.strip()
        if not q:
            continue
        if _is_narrative_prose(q):
            logger.info("query_filtered_prose", query=q[:80])
            continue
        all_queries.append(q)

    # Deduplicate
    seen_queries: set[str] = set()
    search_queries: list[str] = []
    for q in all_queries:
        key = q.lower().strip()
        if key not in seen_queries:
            seen_queries.add(key)
            search_queries.append(q)

    logger.info("research_queries", count=len(search_queries), queries=[q[:60] for q in search_queries])

    # ── Wikipedia research (parallelised) ─────────────────────────────
    seen_titles: set[str] = set()
    filtered_count = 0

    # Step 1: parallel search across all queries
    search_results_by_query: dict[str, list[dict]] = {}

    def _search_one(query: str) -> tuple[str, list[dict]]:
        return query, search_wikipedia(query, limit=5)

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(_search_one, q): q for q in search_queries}
        for future in as_completed(futures):
            query = futures[future]
            try:
                q, results = future.result()
                search_results_by_query[q] = results
            except Exception as e:
                logger.warning("wikipedia_search_error", query=query, error=str(e))

    # Collect unique, relevant titles across all search results
    titles_to_fetch: list[str] = []
    for query in search_queries:
        for r in search_results_by_query.get(query, []):
            title = r["title"]
            if title in seen_titles:
                continue
            if not _passes_relevance_filter(
                title=title,
                snippet=r.get("snippet", ""),
                era=chosen.era,
                geo=chosen.geo,
                core_pov=chosen.core_pov,
                topic_title=chosen.title,
            ):
                filtered_count += 1
                logger.info("result_filtered_irrelevant", title=title, query=query[:60])
                continue
            seen_titles.add(title)
            titles_to_fetch.append(title)

    # Step 2: parallel content + reference fetch for each accepted title
    def _fetch_content(title: str) -> tuple[str, dict, list[str]]:
        content = get_wikipedia_content(title)
        refs: list[str] = []
        try:
            refs = get_wikipedia_references(title)[:5]
        except Exception:
            pass
        return title, content, refs

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(_fetch_content, t): t for t in titles_to_fetch}
        for future in as_completed(futures):
            title = futures[future]
            try:
                _, content, refs = future.result()
                if not content.get("extract"):
                    continue

                corpus.append({
                    "title": content["title"],
                    "text": content["extract"][:8000],
                    "url": content["url"],
                    "source": "Wikipedia",
                    "domain": "wikipedia.org",
                })

                sources.append(SourceEntry(
                    name=f"Wikipedia: {content['title']}",
                    url=content["url"],
                    domain="wikipedia.org",
                    source_type="Secondary",
                    credibility_score=0.75,
                    is_institutional=False,
                ))

                for ref_url in refs:
                    domain = extract_domain(ref_url)
                    sources.append(SourceEntry(
                        name=f"Reference from {content['title']}",
                        url=ref_url,
                        domain=domain,
                        source_type=classify_source_type(ref_url),
                        credibility_score=get_credibility_score(ref_url),
                        is_institutional=is_institutional_source(ref_url),
                    ))
            except Exception as e:
                logger.warning("wikipedia_content_error", title=title, error=str(e))

    if filtered_count:
        logger.info("relevance_filter_summary", filtered=filtered_count)

    # ── Archive research ──────────────────────────────────────────────
    archive_queries = [chosen.title, f"{chosen.core_pov} {chosen.era}"]
    for query in archive_queries:
        try:
            archive_results = search_all_archives(query, limit=3)
            for ar in archive_results:
                corpus.append({
                    "title": ar.get("title", ""),
                    "text": ar.get("description", "")[:4000],
                    "url": ar.get("url", ""),
                    "source": ar.get("source", ""),
                    "domain": ar.get("domain", ""),
                })

                sources.append(SourceEntry(
                    name=f"{ar.get('source', 'Archive')}: {ar.get('title', '')}",
                    url=ar.get("url", ""),
                    domain=ar.get("domain", ""),
                    source_type=classify_source_type(ar.get("url", ""), ar.get("description", "")),
                    credibility_score=get_credibility_score(ar.get("url", "")),
                    is_institutional=is_institutional_source(ar.get("url", "")),
                ))
        except Exception as e:
            logger.warning("archive_search_error", query=query, error=str(e))

    # ── Source credibility filtering (absorbed from SourceCredibilityNode) ─
    errors = list(state.get("errors", []))
    validated_sources: list[SourceEntry] = []
    for source in sources:
        if not source.url:
            continue
        source.credibility_score = get_credibility_score(source.url)
        source.is_institutional = is_institutional_source(source.url)
        if source.credibility_score >= 0.3:
            validated_sources.append(source)
        else:
            logger.warning("low_credibility_source", url=source.url, score=source.credibility_score)

    diversity = validate_source_diversity(
        [{"url": s.url} for s in validated_sources]
    )
    if not diversity["meets_minimum"]:
        errors.append(
            f"Source diversity insufficient: only {diversity['unique_domains']} "
            f"unique domains (need ≥3). Domains: {diversity['domains']}"
        )
    if not diversity["has_institutional"]:
        errors.append("No institutional source (.edu, .gov, archive, museum) found")

    logger.info(
        "research_complete",
        corpus_items=len(corpus),
        sources=len(validated_sources),
        unique_domains=diversity["unique_domains"],
    )

    return {
        "research_corpus": corpus,
        "sources_log": validated_sources,
        "errors": errors,
        "current_node": "ResearchFetchNode",
    }
