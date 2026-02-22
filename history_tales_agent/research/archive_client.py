"""Client for institutional archives (Library of Congress, National Archives, Internet Archive)."""

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
# National Archives (UK)
# ---------------------------------------------------------------------------

TNA_API = "https://discovery.nationalarchives.gov.uk/API/search/v1/records"


@retry_http
def search_national_archives_uk(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Search UK National Archives Discovery API."""
    cache = get_cache()
    cached = cache.get(TNA_API, {"sps.searchQuery": query})
    if cached:
        return cached

    params = {
        "sps.searchQuery": query,
        "sps.resultsPageSize": limit,
    }
    try:
        resp = httpx.get(TNA_API, params=params, timeout=20, headers={**_HEADERS, "Accept": "application/json"})
        resp.raise_for_status()
        data = resp.json()
        results = []
        for rec in data.get("records", []):
            results.append({
                "title": rec.get("title", ""),
                "url": f"https://discovery.nationalarchives.gov.uk/details/r/{rec.get('id', '')}",
                "description": rec.get("scopeContent", {}).get("description", ""),
                "date": rec.get("coveringDates", ""),
                "source": "The National Archives (UK)",
                "domain": "nationalarchives.gov.uk",
            })
        cache.set(TNA_API, results, {"sps.searchQuery": query})
        logger.info("tna_search", query=query, results=len(results))
        return results
    except Exception as e:
        logger.warning("tna_search_failed", query=query, error=str(e))
        return []


# ---------------------------------------------------------------------------
# Aggregated search
# ---------------------------------------------------------------------------


def search_all_archives(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """Search all supported archives and return combined results."""
    results: list[dict[str, Any]] = []
    results.extend(search_library_of_congress(query, limit))
    results.extend(search_internet_archive(query, limit))
    results.extend(search_national_archives_uk(query, limit))
    logger.info("all_archives_search", query=query, total_results=len(results))
    return results
