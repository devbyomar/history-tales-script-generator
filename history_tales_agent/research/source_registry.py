"""Source registry and credibility heuristics."""

from __future__ import annotations

from urllib.parse import urlparse

from history_tales_agent.config import ALLOWED_SOURCE_DOMAINS, FORBIDDEN_PATTERNS
from history_tales_agent.utils.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Credibility tiers
# ---------------------------------------------------------------------------

TIER_1_DOMAINS = {
    "archives.gov", "nationalarchives.gov.uk", "loc.gov",
    "iwm.org.uk", "nara.gov", "smithsonianmag.com",
}

TIER_2_DOMAINS = {
    "wikipedia.org", "archive.org", "europeana.eu",
    "bbc.co.uk", "history.com", "wikidata.org",
}

INSTITUTIONAL_SUFFIXES = (".edu", ".gov", ".gov.uk", ".ac.uk")


def extract_domain(url: str) -> str:
    """Extract the domain from a URL."""
    try:
        parsed = urlparse(url)
        return parsed.netloc.lower().lstrip("www.")
    except Exception:
        return ""


def is_allowed_source(url: str) -> bool:
    """Check if a URL is from an allowed source domain."""
    domain = extract_domain(url)
    if not domain:
        return False

    # Check forbidden patterns
    url_lower = url.lower()
    for pattern in FORBIDDEN_PATTERNS:
        if pattern in url_lower:
            logger.warning("forbidden_source", url=url, pattern=pattern)
            return False

    # Check allowed domains
    for allowed in ALLOWED_SOURCE_DOMAINS:
        if allowed in domain or domain.endswith(allowed):
            return True

    return False


def is_institutional_source(url: str) -> bool:
    """Check if a source is institutional (.edu, .gov, archive, museum)."""
    domain = extract_domain(url)
    for suffix in INSTITUTIONAL_SUFFIXES:
        if domain.endswith(suffix):
            return True
    for tier1 in TIER_1_DOMAINS:
        if tier1 in domain:
            return True
    return False


def get_credibility_score(url: str) -> float:
    """Score source credibility from 0.0 to 1.0."""
    domain = extract_domain(url)

    if not domain:
        return 0.0

    # Check forbidden
    for pattern in FORBIDDEN_PATTERNS:
        if pattern in url.lower():
            return 0.0

    # Tier 1: primary archives & government
    for t1 in TIER_1_DOMAINS:
        if t1 in domain:
            return 0.95

    # Institutional
    for suffix in INSTITUTIONAL_SUFFIXES:
        if domain.endswith(suffix):
            return 0.90

    # Tier 2: major encyclopedias & outlets
    for t2 in TIER_2_DOMAINS:
        if t2 in domain:
            return 0.75

    # Allowed but lower tier
    for allowed in ALLOWED_SOURCE_DOMAINS:
        if allowed in domain:
            return 0.65

    return 0.3  # Unknown source


def classify_source_type(url: str, description: str = "") -> str:
    """Classify as Primary, Secondary, or Derived."""
    domain = extract_domain(url)
    desc_lower = description.lower()

    # Primary: direct government/archive records
    primary_indicators = [
        "archives.gov", "nationalarchives.gov.uk", "nara.gov",
        "loc.gov/resource", "loc.gov/item",
    ]
    for indicator in primary_indicators:
        if indicator in url.lower():
            return "Primary"

    if any(kw in desc_lower for kw in ["original document", "primary source", "declassified", "official record"]):
        return "Primary"

    # Derived: blog-style or commentary
    if any(kw in desc_lower for kw in ["blog", "opinion", "commentary", "editorial"]):
        return "Derived"

    return "Secondary"


def validate_source_diversity(sources: list[dict]) -> dict[str, any]:
    """Check that we have minimum source diversity."""
    domains = set()
    has_institutional = False
    for src in sources:
        url = src.get("url", "")
        domain = extract_domain(url)
        domains.add(domain)
        if is_institutional_source(url):
            has_institutional = True

    return {
        "unique_domains": len(domains),
        "meets_minimum": len(domains) >= 3,
        "has_institutional": has_institutional,
        "domains": list(domains),
    }
