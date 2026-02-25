"""Client for institutional archives (Library of Congress, Internet Archive, Europeana, DPLA, Trove)."""

from __future__ import annotations

from typing import Any

import httpx

from history_tales_agent.utils.cache import get_cache
from history_tales_agent.utils.logging import get_logger
from history_tales_agent.utils.retry import retry_http

logger = get_logger(__name__)

_HEADERS = {
    "User-Agent": "HistoryTalesScriptGenerator/1.0 (https://github.com/devbyomar/history-tales-script-generator; educational research bot)",
}

# ---------------------------------------------------------------------------
# Library of Congress
# ---------------------------------------------------------------------------

LOC_API = "https://www.loc.gov/search/"


@retry_http
def search_library_of_congress(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Search Library of Congress digital collections."""
    cache = get_cache()
    cached = cache.get(LOC_API, {"q": query})
    if cached:
        return cached

    params = {
        "q": query,
        "fo": "json",
        "c": limit,
    }
    try:
        resp = httpx.get(LOC_API, params=params, timeout=20, follow_redirects=True, headers=_HEADERS)
        resp.raise_for_status()
        data = resp.json()
        results = []
        for item in data.get("results", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", item.get("id", "")),
                "description": item.get("description", [""])[0] if isinstance(item.get("description"), list) else item.get("description", ""),
                "date": item.get("date", ""),
                "source": "Library of Congress",
                "domain": "loc.gov",
            })
        cache.set(LOC_API, results, {"q": query})
        logger.info("loc_search", query=query, results=len(results))
        return results
    except Exception as e:
        logger.warning("loc_search_failed", query=query, error=str(e))
        return []


# ---------------------------------------------------------------------------
# Internet Archive
# ---------------------------------------------------------------------------

ARCHIVE_API = "https://archive.org/advancedsearch.php"


@retry_http
def search_internet_archive(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Search Internet Archive for historical documents."""
    cache = get_cache()
    cached = cache.get(ARCHIVE_API, {"q": query})
    if cached:
        return cached

    params = {
        "q": query,
        "fl[]": ["identifier", "title", "description", "date"],
        "rows": limit,
        "output": "json",
    }
    try:
        resp = httpx.get(ARCHIVE_API, params=params, timeout=20, headers=_HEADERS)
        resp.raise_for_status()
        data = resp.json()
        results = []
        for doc in data.get("response", {}).get("docs", []):
            results.append({
                "title": doc.get("title", ""),
                "url": f"https://archive.org/details/{doc.get('identifier', '')}",
                "description": doc.get("description", ""),
                "date": doc.get("date", ""),
                "source": "Internet Archive",
                "domain": "archive.org",
            })
        cache.set(ARCHIVE_API, results, {"q": query})
        logger.info("archive_search", query=query, results=len(results))
        return results
    except Exception as e:
        logger.warning("archive_search_failed", query=query, error=str(e))
        return []


# ---------------------------------------------------------------------------
# Europeana (European cultural heritage — free API, no key needed for basic)
# ---------------------------------------------------------------------------

EUROPEANA_API = "https://api.europeana.eu/record/v2/search.json"
# Free tier key for open-source/educational use (1000 req/day)
_EUROPEANA_KEY = "api2demo"


@retry_http
def search_europeana(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Search Europeana collections for historical records."""
    cache = get_cache()
    cached = cache.get(EUROPEANA_API, {"query": query})
    if cached:
        return cached

    params = {
        "wskey": _EUROPEANA_KEY,
        "query": query,
        "rows": limit,
        "profile": "standard",
    }
    try:
        resp = httpx.get(EUROPEANA_API, params=params, timeout=20, headers=_HEADERS)
        resp.raise_for_status()
        data = resp.json()
        results = []
        for item in data.get("items", []):
            title_list = item.get("title", [""])
            title = title_list[0] if isinstance(title_list, list) else str(title_list)
            desc_list = item.get("dcDescription", [""])
            desc = desc_list[0] if isinstance(desc_list, list) else str(desc_list)
            guid = item.get("guid", item.get("link", ""))
            results.append({
                "title": title,
                "url": guid,
                "description": desc,
                "date": item.get("year", [""])[0] if isinstance(item.get("year"), list) else str(item.get("year", "")),
                "source": "Europeana",
                "domain": "europeana.eu",
            })
        cache.set(EUROPEANA_API, results, {"query": query})
        logger.info("europeana_search", query=query, results=len(results))
        return results
    except Exception as e:
        logger.warning("europeana_search_failed", query=query, error=str(e))
        return []


# ---------------------------------------------------------------------------
# Aggregated search
# ---------------------------------------------------------------------------


def search_all_archives(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """Search all supported archives and return combined results."""
    results: list[dict[str, Any]] = []
    results.extend(search_library_of_congress(query, limit))
    results.extend(search_internet_archive(query, limit))
    results.extend(search_europeana(query, limit))
    logger.info("all_archives_search", query=query, total_results=len(results))
    return results
