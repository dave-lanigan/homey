"""Filter-keyed cache of Airbnb search result URL sets.

When the same structured search filters are used again, ``run_search`` can
hydrate listing details from Turso instead of re-scraping Airbnb.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from sqlmodel import select

from api.db import get_session, init_db
from api.models import Listing, SearchCache, utcnow
from api.tools.listing_urls import normalize_listing_url

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../../.env"))

SEARCH_CACHE_TTL_HOURS = max(0, int(os.getenv("SEARCH_CACHE_TTL_HOURS", "24")))
# Increment whenever the SERP extraction semantics change. This prevents URL
# sets collected with older (for example, date-less) requests from being reused.
SEARCH_CACHE_VERSION = 2

# Params that change which Airbnb SERP / listing set is returned.
# Keywords are applied after the scrape, so they are not part of the key.
_SCRAPE_KEY_FIELDS = (
    "location",
    "checkin",
    "checkout",
    "nights",
    "guests",
    "room_type",
    "amenities",
    "min_price",
    "max_price",
    "min_rating",
    "superhost",
    "instant_book",
    "self_checkin",
    "min_bedrooms",
    "min_beds",
    "min_bathrooms",
    "max_listings",
    "max_pages",
)


def scrape_filter_key(params, *, checkout: str | None = None) -> str:
    """Stable hash of the structured filters that drive Airbnb scraping."""
    payload = {"version": SEARCH_CACHE_VERSION}
    for field in _SCRAPE_KEY_FIELDS:
        value = getattr(params, field, None)
        if field == "checkout" and checkout is not None:
            value = checkout
        if isinstance(value, list):
            value = sorted(str(v) for v in value)
        payload[field] = value
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_cached_urls(filter_key: str) -> list[str] | None:
    """Return cached listing URLs when the entry exists and is within TTL."""
    init_db()
    with get_session() as session:
        row = session.get(SearchCache, filter_key)
        if row is None:
            return None
        if SEARCH_CACHE_TTL_HOURS > 0:
            created = row.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            age = datetime.now(timezone.utc) - created.astimezone(timezone.utc)
            if age > timedelta(hours=SEARCH_CACHE_TTL_HOURS):
                session.delete(row)
                session.commit()
                return None
        try:
            urls = json.loads(row.urls)
        except json.JSONDecodeError:
            return None
        return [u for u in urls if isinstance(u, str) and u]


def set_cached_urls(filter_key: str, urls: list[str], search_url: str = "") -> None:
    """Upsert the URL set for a filter fingerprint.

    Only call this when detail scrape produced listings. Caching SERP URLs alone
    poisons later searches: hydrate finds nothing and every call re-scrapes.
    """
    init_db()
    now = utcnow()
    normalized = list(
        dict.fromkeys(normalize_listing_url(url) for url in urls if normalize_listing_url(url))
    )
    if not normalized:
        return
    with get_session() as session:
        row = session.get(SearchCache, filter_key)
        payload = json.dumps(normalized)
        if row is None:
            session.add(
                SearchCache(
                    filter_key=filter_key,
                    search_url=search_url,
                    urls=payload,
                    created_at=now,
                )
            )
        else:
            row.search_url = search_url
            row.urls = payload
            row.created_at = now
        session.commit()


def clear_cached_urls(filter_key: str) -> None:
    """Drop a poisoned or failed filter cache entry."""
    init_db()
    with get_session() as session:
        row = session.get(SearchCache, filter_key)
        if row is not None:
            session.delete(row)
            session.commit()


def load_listings_by_urls(urls: list[str]) -> tuple[list[dict], list[str]]:
    """Load listing dicts from Turso in ``urls`` order.

    Returns ``(found, missing_urls)``. Found entries use the same shape as the
    scraper so callers can run keyword filters unchanged. URL matching is by
    canonical room id so query-param variants still hydrate.
    """
    if not urls:
        return [], []

    ordered = [normalize_listing_url(url) for url in urls]
    ordered = [url for url in ordered if url]
    init_db()
    with get_session() as session:
        rows = session.exec(select(Listing)).all()

    by_norm: dict[str, Listing] = {}
    for row in rows:
        norm = normalize_listing_url(row.url)
        prior = by_norm.get(norm)
        if prior is None or (row.updated_at or row.created_at) >= (
            prior.updated_at or prior.created_at
        ):
            by_norm[norm] = row

    found: list[dict] = []
    missing: list[str] = []
    for url in ordered:
        row = by_norm.get(url)
        if row is None:
            missing.append(url)
            continue
        found.append(
            {
                "url": url,
                "title": row.title,
                "city": row.city,
                "description": row.description,
                "price": row.price,
                "total_price": row.total_price,
                "rating": row.rating,
                "amenities": json.loads(row.amenities or "[]"),
                "house_rules": json.loads(row.house_rules or "[]"),
                "image_url": row.image_url,
                "image_urls": json.loads(row.image_urls or "[]"),
                "full_text": row.full_text,
                "matched_keywords": json.loads(row.matched_keywords or "[]"),
            }
        )
    return found, missing
