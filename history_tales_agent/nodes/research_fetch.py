"""ResearchFetchNode — gathers research from multiple credible sources."""

from __future__ import annotations

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
)
from history_tales_agent.utils.logging import get_logger

logger = get_logger(__name__)


def research_fetch_node(state: dict[str, Any]) -> dict[str, Any]:
    """Fetch research from Wikipedia, archives, and institutional sources."""
    logger.info("node_start", node="ResearchFetchNode")

    chosen: TopicCandidate | None = state.get("chosen_topic")
    if not chosen:
        return {
            "errors": state.get("errors", []) + ["ResearchFetchNode: No chosen topic"],
            "current_node": "ResearchFetchNode",
        }

    corpus: list[dict[str, Any]] = []
    sources: list[SourceEntry] = []

    # --- Wikipedia research ---
    search_queries = [
        chosen.title,
        chosen.core_pov,
        f"{chosen.era} {chosen.geo}",
    ]
    # Add twist points as search queries
    for twist in chosen.twist_points[:3]:
        search_queries.append(twist)

    seen_titles = set()
    for query in search_queries:
        try:
            results = search_wikipedia(query, limit=5)
            for r in results:
                title = r["title"]
                if title in seen_titles:
                    continue
                seen_titles.add(title)

                content = get_wikipedia_content(title)
                if not content.get("extract"):
                    continue

                corpus.append({
                    "title": content["title"],
                    "text": content["extract"][:8000],  # Cap length
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

                # Get external references
                try:
                    refs = get_wikipedia_references(title)
                    for ref_url in refs[:5]:
                        domain = extract_domain(ref_url)
                        sources.append(SourceEntry(
                            name=f"Reference from {content['title']}",
                            url=ref_url,
                            domain=domain,
                            source_type=classify_source_type(ref_url),
                            credibility_score=get_credibility_score(ref_url),
                            is_institutional=is_institutional_source(ref_url),
                        ))
                except Exception:
                    pass

        except Exception as e:
            logger.warning("wikipedia_search_error", query=query, error=str(e))

    # --- Archive research ---
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

    logger.info("research_complete", corpus_items=len(corpus), sources=len(sources))

    return {
        "research_corpus": corpus,
        "sources_log": sources,
        "current_node": "ResearchFetchNode",
    }
