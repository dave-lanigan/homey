"""
Multimodal embedding search for Airbnb listings using Gemini.

Uses gemini-embedding-2 to embed listings and user queries, then ranks by
cosine similarity. Listing metadata and their vectors are stored in Turso
via SQLModel, keyed by listing URL.
"""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

from dotenv import load_dotenv
from google import genai
from google.genai import types
from sqlmodel import select

from api.db import get_session, init_db
from api.models import Embedding, Listing, utcnow

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../../.env"))

EMBED_MODEL = os.getenv("GEMINI_EMBED_MODEL", "gemini-embedding-2")
EMBED_CONCURRENCY = max(1, int(os.getenv("GEMINI_EMBED_CONCURRENCY", "5")))

DOCUMENT_TASK_TYPE = "RETRIEVAL_DOCUMENT"
QUERY_TASK_TYPE = "RETRIEVAL_QUERY"
EmbeddingTaskType = Literal["RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"]


@dataclass
class SearchResult:
    """A ranked search result."""

    listing_id: str
    title: str
    url: str
    city: str
    similarity_score: float
    description: str = ""
    price: Optional[float] = None
    rating: Optional[float] = None
    amenities: list[str] = field(default_factory=list)
    house_rules: list[str] = field(default_factory=list)
    image_url: Optional[str] = None
    image_urls: list = field(default_factory=list)
    vision_score: Optional[float] = None


# ============================================================================
# Turso / SQLModel storage
# ============================================================================


def store_listings(listings: list[dict]) -> int:
    """Upsert listing rows by URL. Returns the number of rows written."""
    init_db()
    written = 0
    with get_session() as session:
        for l in listings:
            url = l.get("url") or l.get("listing_id")
            if not url:
                continue

            row = session.get(Listing, url)
            now = utcnow()
            fields = {
                "title": l.get("title", ""),
                "city": l.get("city", ""),
                "description": l.get("description", ""),
                "price": l.get("price"),
                "rating": l.get("rating"),
                "amenities": json.dumps(l.get("amenities") or []),
                "house_rules": json.dumps(l.get("house_rules") or []),
                "image_url": l.get("image_url", ""),
                "image_urls": json.dumps(l.get("image_urls") or []),
                "full_text": l.get("full_text", ""),
                "matched_keywords": json.dumps(l.get("matched_keywords") or []),
                "updated_at": now,
            }
            if row is None:
                session.add(Listing(url=url, created_at=now, **fields))
            else:
                for key, value in fields.items():
                    setattr(row, key, value)
            written += 1
        session.commit()
    return written


def embedded_urls() -> set[str]:
    """Return URLs with a current retrieval-document embedding."""
    init_db()
    with get_session() as session:
        rows = session.exec(
            select(Embedding.url).where(
                Embedding.model == EMBED_MODEL,
                Embedding.task_type == DOCUMENT_TASK_TYPE,
            )
        ).all()
        return set(rows)


def _store_embedding(
    url: str,
    vector: list,
    model: str,
    task_type: EmbeddingTaskType,
) -> None:
    with get_session() as session:
        now = utcnow()
        row = session.get(Embedding, url)
        if row is None:
            session.add(
                Embedding(
                    url=url,
                    vector=json.dumps(vector),
                    model=model,
                    task_type=task_type,
                    created_at=now,
                    updated_at=now,
                )
            )
        else:
            row.vector = json.dumps(vector)
            row.model = model
            row.task_type = task_type
            row.updated_at = now
        session.commit()


def load_indexed_listings() -> list[dict]:
    """Return all listings that have an embedding, with their vectors."""
    init_db()
    with get_session() as session:
        rows = session.exec(
            select(Listing, Embedding)
            .join(Embedding, Embedding.url == Listing.url)
            .where(
                Embedding.model == EMBED_MODEL,
                Embedding.task_type == DOCUMENT_TASK_TYPE,
            )
        ).all()

        listings = []
        for listing, embedding in rows:
            listings.append(
                {
                    "listing_id": listing.url,
                    "url": listing.url,
                    "title": listing.title,
                    "city": listing.city,
                    "description": listing.description,
                    "price": listing.price,
                    "rating": listing.rating,
                    "amenities": json.loads(listing.amenities),
                    "house_rules": json.loads(listing.house_rules),
                    "image_url": listing.image_url,
                    "image_urls": json.loads(listing.image_urls),
                    "full_text": listing.full_text,
                    "matched_keywords": json.loads(listing.matched_keywords),
                    "embedding": json.loads(embedding.vector),
                }
            )
        return listings


def clear_index() -> None:
    """Delete all stored listings and embeddings."""
    init_db()
    with get_session() as session:
        for row in session.exec(select(Embedding)).all():
            session.delete(row)
        for row in session.exec(select(Listing)).all():
            session.delete(row)
        session.commit()


# ============================================================================
# Embedding helpers
# ============================================================================


def _load_image_bytes(image_path: str) -> bytes:
    with open(image_path, "rb") as f:
        return f.read()


def _get_image_mime_type(image_path: str) -> str:
    ext = Path(image_path).suffix.lower()
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    return mime_map.get(ext, "image/jpeg")


def embed_text(
    text: str,
    task_type: EmbeddingTaskType,
    client: genai.Client = None,
) -> list:
    """Embed text for its explicit document or query retrieval role."""
    if client is None:
        client = genai.Client()
    result = client.models.embed_content(
        model=f"models/{EMBED_MODEL}",
        contents=[text],
        config=types.EmbedContentConfig(task_type=task_type),
    )
    return result.embeddings[0].values


def embed_image(image_path: str, client: genai.Client = None) -> list:
    """Embed an image file using the Gemini embedding model."""
    if client is None:
        client = genai.Client()
    result = client.models.embed_content(
        model=f"models/{EMBED_MODEL}",
        contents=[
            types.Part.from_bytes(
                data=_load_image_bytes(image_path),
                mime_type=_get_image_mime_type(image_path),
            )
        ],
    )
    return result.embeddings[0].values


def embed_multimodal(
    image_path: Optional[str] = None,
    image_data: Optional[bytes] = None,
    image_media_type: Optional[str] = None,
    text: Optional[str] = None,
    task_type: EmbeddingTaskType = QUERY_TASK_TYPE,
    client: genai.Client = None,
) -> list:
    """Embed a query made from image and/or text."""
    if client is None:
        client = genai.Client()

    parts = []
    if text:
        parts.append(text)
    if image_path:
        parts.append(
            types.Part.from_bytes(
                data=_load_image_bytes(image_path),
                mime_type=_get_image_mime_type(image_path),
            )
        )
    if image_data:
        parts.append(
            types.Part.from_bytes(
                data=image_data,
                mime_type=image_media_type or "image/jpeg",
            )
        )
    if not parts:
        raise ValueError("Must provide text or an image")

    result = client.models.embed_content(
        model=f"models/{EMBED_MODEL}",
        contents=parts,
        config=types.EmbedContentConfig(task_type=task_type),
    )
    return result.embeddings[0].values


def cosine_similarity(vec1: list, vec2: list) -> float:
    """Cosine similarity between two vectors (pure Python, no numpy)."""
    if not vec1 or not vec2:
        return 0.0
    dot = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = sum(a * a for a in vec1) ** 0.5
    norm2 = sum(b * b for b in vec2) ** 0.5
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


def _locations_match(query: str, listing_city: str) -> bool:
    """Match a city with or without a trailing state/country qualifier."""
    query_normalized = " ".join(query.casefold().split())
    city_normalized = " ".join(listing_city.casefold().split())
    return (
        query_normalized == city_normalized
        or city_normalized.startswith(f"{query_normalized},")
        or query_normalized.startswith(f"{city_normalized},")
    )


# ============================================================================
# Indexing
# ============================================================================


def build_listing_text(listing: dict) -> str:
    """Compose the text used to embed a listing."""
    parts = [listing.get("title", "")]
    if listing.get("city"):
        parts.append(f"Location: {listing['city']}")
    if listing.get("description"):
        parts.append(listing["description"])
    if listing.get("amenities"):
        parts.append("Amenities: " + ", ".join(listing["amenities"]))
    if listing.get("full_text"):
        parts.append(listing["full_text"][:3000])
    return "\n".join(parts)


def create_listing_embedding(listing: dict, client: genai.Client = None) -> list:
    """Embed a listing as a retrieval document and return its vector."""
    if client is None:
        client = genai.Client()
    text_to_embed = build_listing_text(listing)
    return embed_text(text_to_embed, DOCUMENT_TASK_TYPE, client)


def index_listings(listings: list[dict], client: genai.Client = None, force: bool = False) -> int:
    """
    Index a batch of listings into Turso.

    Listing rows are always upserted; embeddings are only computed for URLs
    that don't have one yet (unless ``force`` is True). Returns the number of
    new embeddings created.
    """
    if client is None:
        client = genai.Client()

    store_listings(listings)

    seen = set() if force else embedded_urls()
    pending: list[tuple[str, dict]] = []
    for listing in listings:
        url = listing.get("url") or listing.get("listing_id")
        if not url:
            continue
        if url in seen:
            continue
        pending.append((url, listing))
        seen.add(url)

    def create_pending_embedding(item: tuple[str, dict]) -> tuple[str, list]:
        url, listing = item
        return url, create_listing_embedding(listing, client)

    # Gemini requests run concurrently; Turso writes stay serialized afterward.
    with ThreadPoolExecutor(max_workers=min(EMBED_CONCURRENCY, len(pending) or 1)) as executor:
        generated = executor.map(create_pending_embedding, pending)
        for url, vector in generated:
            _store_embedding(
                url,
                vector,
                EMBED_MODEL,
                DOCUMENT_TASK_TYPE,
            )

    return len(pending)


# ============================================================================
# Search
# ============================================================================


def search_listings(
    query_text: Optional[str] = None,
    query_image_path: Optional[str] = None,
    query_image_data: Optional[bytes] = None,
    query_image_media_type: Optional[str] = None,
    city: Optional[str] = None,
    top_k: int = 10,
    urls: Optional[set] = None,
    client: genai.Client = None,
) -> list[SearchResult]:
    """
    Search indexed listings by embedding similarity.

    Args:
        query_text: Text description of what to search for
        query_image_path: Path to an image to search with
        city: Optional city filter (case-insensitive)
        top_k: Number of results to return
        urls: Optional set of listing URLs to restrict the search to
        client: Gemini client instance

    Returns:
        Ranked list of SearchResult objects
    """
    if client is None:
        client = genai.Client()

    if not query_text and not query_image_path and not query_image_data:
        raise ValueError("Must provide text or an image")

    query_embedding = embed_multimodal(
        image_path=query_image_path,
        image_data=query_image_data,
        image_media_type=query_image_media_type,
        text=query_text,
        task_type=QUERY_TASK_TYPE,
        client=client,
    )

    indexed = load_indexed_listings()
    if not indexed:
        raise ValueError("No indexed listings. Run the search flow first to index listings.")

    scores = []
    for listing in indexed:
        if city and listing["city"] and not _locations_match(city, listing["city"]):
            continue
        if urls is not None and listing["url"] not in urls:
            continue
        similarity = cosine_similarity(query_embedding, listing["embedding"])
        scores.append((listing, similarity))

    scores.sort(key=lambda x: x[1], reverse=True)

    results = []
    for listing, similarity in scores[:top_k]:
        results.append(
            SearchResult(
                listing_id=listing["listing_id"],
                title=listing["title"],
                url=listing["url"],
                city=listing["city"],
                similarity_score=similarity,
                description=listing["description"],
                price=listing.get("price"),
                rating=listing.get("rating"),
                amenities=listing.get("amenities") or [],
                house_rules=listing.get("house_rules") or [],
                image_url=listing["image_url"],
                image_urls=listing["image_urls"],
            )
        )
    return results


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--clear":
        clear_index()
        print("Index cleared.")
    elif len(sys.argv) > 1 and sys.argv[1] == "--count":
        print(f"{len(load_indexed_listings())} indexed listings")
    else:
        print("embedding_search.py usage:")
        print("  python -m api.tools.embedding_search --clear   wipe the index")
        print("  python -m api.tools.embedding_search --count   show indexed listing count")
