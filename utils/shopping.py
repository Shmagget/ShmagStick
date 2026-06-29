"""Affiliate shopping link generation.

Constructs Amazon URLs with the ShmagStick Amazon Associates tracking tag.
The code can ensure Amazon links carry the tag, but Amazon alone determines
whether a click qualifies for commission under its Associates rules.
"""

from __future__ import annotations

from urllib.parse import parse_qsl, quote_plus, urlencode, urlparse, urlunparse


DEFAULT_AMAZON_ASSOCIATE_TAG = "shmagstick-20"


# Affiliate tags per Amazon TLD
TAGS = {
    "com": DEFAULT_AMAZON_ASSOCIATE_TAG,
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
        loc = locale.getlocale()[0] or ""
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
    return TAGS.get(tld) or DEFAULT_AMAZON_ASSOCIATE_TAG


def _tag_for_tld(tld: str) -> tuple[str, str]:
    tag = TAGS.get(tld, "")
    if tag:
        return tld, tag
    return "com", DEFAULT_AMAZON_ASSOCIATE_TAG


def is_amazon_url(url: str) -> bool:
    host = (urlparse(url or "").netloc or "").lower()
    return host.startswith("amazon.") or host.startswith("www.amazon.") or ".amazon." in host


def ensure_amazon_affiliate_tag(url: str) -> str:
    """Return an Amazon URL with the active Associates tag applied.

    Non-Amazon URLs are returned unchanged. Existing Amazon `tag` values are
    replaced with the configured ShmagStick tag to avoid stale or untagged
    upgrade links reaching the GUI/report.
    """
    parsed = urlparse(url or "")
    if parsed.scheme not in ("http", "https") or not is_amazon_url(url):
        return url

    host = parsed.netloc.lower()
    tld = "com"
    marker = "amazon."
    if marker in host:
        tld = host.split(marker, 1)[1].split(":", 1)[0]
    tld, tag = _tag_for_tld(tld)

    netloc = f"www.amazon.{tld}"
    query = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True) if key.lower() != "tag"]
    query.append(("tag", tag))
    return urlunparse((parsed.scheme or "https", netloc, parsed.path, parsed.params, urlencode(query), parsed.fragment))


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
    tld = get_amazon_tld()
    tld, tag = _tag_for_tld(tld)

    if asin:
        url = f"https://www.amazon.{tld}/dp/{asin}"
        return ensure_amazon_affiliate_tag(url)

    url = f"https://www.amazon.{tld}/s?k={quote_plus(query)}"
    return ensure_amazon_affiliate_tag(url)
