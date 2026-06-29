"""Affiliate shopping link generation.

Constructs Amazon URLs with regional affiliate tags.
"""

from __future__ import annotations

# Affiliate tags per Amazon TLD
TAGS = {
    "com": "shmagstick-20",
    "co.uk": "",
    "ca": "",
    "com.au": "",
    "de": "",
    "fr": "",
    "it": "",
    "es": "",
    "in": "",
    "co.jp": "",
    "nl": "",
    "se": "",
    "pl": "",
    "com.mx": "",
    "com.br": "",
    "sg": "",
    "ae": "",
}

TLD_MAP = {
    "US": "com", "GB": "co.uk", "CA": "ca", "AU": "com.au",
    "DE": "de", "FR": "fr", "IT": "it", "ES": "es", "NL": "nl",
    "SE": "se", "PL": "pl", "IN": "in", "JP": "co.jp",
    "MX": "com.mx", "BR": "com.br", "SG": "sg", "AE": "ae",
}

# Best-effort region detection
def _detect_tld() -> str:
    try:
        from PyQt6.QtCore import QLocale
        loc = QLocale()
        country = loc.territoryToString(loc.country())
        # QLocale country codes are numeric; try OS-level
    except Exception:
        pass
    try:
        import locale
        loc = locale.getdefaultlocale()[0] or ""
        for code, tld in TLD_MAP.items():
            if code in loc.upper():
                return tld
    except Exception:
        pass
    # Fallback: use OS platform's geographic hints
    try:
        import time
        tz = time.tzname[0] if time.tzname else ""
    except Exception:
        tz = ""
    return "com"


_current_tld: str | None = None


def get_amazon_tld() -> str:
    global _current_tld
    if _current_tld is None:
        _current_tld = _detect_tld()
    return _current_tld


def get_tag() -> str:
    tld = get_amazon_tld()
    return TAGS.get(tld, TAGS.get("com", ""))


def shop(query: str, asin: str = "") -> str:
    """Build an Amazon shopping URL carrying the affiliate tag.

    Args:
        query: Search query string (URL-encoded automatically).
        asin: Optional Amazon ASIN for a direct product link.

    Returns:
        Full affiliate URL. Falls back to the US store/tag when the detected
        region has no associate tag of its own, so the affiliate code is
        always applied.
    """
    from urllib.parse import quote_plus

    tld = get_amazon_tld()
    tag = TAGS.get(tld, "")
    if not tag and TAGS.get("com"):
        tld, tag = "com", TAGS["com"]

    if asin:
        url = f"https://www.amazon.{tld}/dp/{asin}"
        return f"{url}/?tag={tag}" if tag else url

    url = f"https://www.amazon.{tld}/s?k={quote_plus(query)}"
    return f"{url}&tag={tag}" if tag else url
