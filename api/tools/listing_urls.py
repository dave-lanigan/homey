"""Canonical Airbnb listing URL helpers."""

from __future__ import annotations

import re

_ROOM_ID_RE = re.compile(r"/rooms/(\d+)")


def listing_room_id(url: str | None) -> str | None:
    """Extract the numeric Airbnb room id from a listing URL."""
    if not url:
        return None
    match = _ROOM_ID_RE.search(url)
    return match.group(1) if match else None


def normalize_listing_url(url: str | None) -> str:
    """Strip tracking/query params so the same room always shares one key.

    Airbnb SERP links look like ``/rooms/123?adults=2&check_in=...``. Using those
    raw hrefs as DB keys creates duplicate rows and breaks embedding reuse across
    searches with different dates/guests.
    """
    if not url:
        return ""
    room_id = listing_room_id(url)
    if room_id:
        return f"https://www.airbnb.com/rooms/{room_id}"
    if url.startswith("/"):
        url = "https://www.airbnb.com" + url
    return url.split("?")[0].split("#")[0]
