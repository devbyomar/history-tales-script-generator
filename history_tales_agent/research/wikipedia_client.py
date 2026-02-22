"""Wikipedia & Wikidata research client."""

from __future__ import annotations

from typing import Any, Optional

import httpx

from history_tales_agent.utils.cache import get_cache
from history_tales_agent.utils.logging import get_logger
from history_tales_agent.utils.retry import retry_http

logger = get_logger(__name__)

WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"

# Wikipedia requires a descriptive User-Agent per their API policy:
# https://meta.wikimedia.org/wiki/User-Agent_policy
_HEADERS = {
    "User-Agent": "HistoryTalesScriptGenerator/1.0 (https://github.com/devbyomar/history-tales-script-generator; educational research bot)",
}


@retry_http
def search_wikipedia(query: str, limit: int = 10) -> list[dict[str, str]]:
    """Search Wikipedia and return a list of {title, snippet, pageid}."""
    cache = get_cache()
    cached = cache.get(WIKIPEDIA_API, {"action": "query", "srsearch": query})
    if cached:
        return cached

    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srlimit": limit,
        "format": "json",
    }
    resp = httpx.get(WIKIPEDIA_API, params=params, timeout=15, headers=_HEADERS)
    resp.raise_for_status()
    data = resp.json()
    results = [
        {
            "title": r["title"],
            "snippet": r.get("snippet", ""),
            "pageid": str(r["pageid"]),
        }
        for r in data.get("query", {}).get("search", [])
    ]
    cache.set(WIKIPEDIA_API, results, {"action": "query", "srsearch": query})
    logger.info("wikipedia_search", query=query, results=len(results))
    return results


@retry_http
def get_wikipedia_content(title: str) -> dict[str, Any]:
    """Fetch full Wikipedia article content (extract) by title."""
    cache = get_cache()
    cache_key = f"wp_content_{title}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    params = {
        "action": "query",
        "titles": title,
        "prop": "extracts|references|links|categories",
        "explaintext": True,
        "format": "json",
    }
    resp = httpx.get(WIKIPEDIA_API, params=params, timeout=30, headers=_HEADERS)
    resp.raise_for_status()
    data = resp.json()

    pages = data.get("query", {}).get("pages", {})
    page = next(iter(pages.values()), {})
    result = {
        "title": page.get("title", title),
        "extract": page.get("extract", ""),
        "pageid": page.get("pageid", ""),
        "url": f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
        "categories": [c["title"] for c in page.get("categories", [])],
    }

    cache.set(cache_key, result)
    logger.info("wikipedia_content", title=title, length=len(result["extract"]))
    return result


@retry_http
def get_wikipedia_references(title: str) -> list[str]:
    """Extract external links from a Wikipedia article."""
    params = {
        "action": "query",
        "titles": title,
        "prop": "extlinks",
        "ellimit": 50,
        "format": "json",
    }
    resp = httpx.get(WIKIPEDIA_API, params=params, timeout=15, headers=_HEADERS)
    resp.raise_for_status()
    data = resp.json()
    pages = data.get("query", {}).get("pages", {})
    page = next(iter(pages.values()), {})
    links = [link.get("*", link.get("url", "")) for link in page.get("extlinks", [])]
    return [l for l in links if l]


@retry_http
def search_wikidata(query: str, limit: int = 5) -> list[dict[str, str]]:
    """Search Wikidata for entities."""
    params = {
        "action": "wbsearchentities",
        "search": query,
        "language": "en",
        "limit": limit,
        "format": "json",
    }
    resp = httpx.get(WIKIDATA_API, params=params, timeout=15, headers=_HEADERS)
    resp.raise_for_status()
    data = resp.json()
    return [
        {
            "id": r["id"],
            "label": r.get("label", ""),
            "description": r.get("description", ""),
            "url": r.get("concepturi", ""),
        }
        for r in data.get("search", [])
    ]
