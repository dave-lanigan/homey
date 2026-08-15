"""
Multimodal embedding search for Airbnb listings using Gemini.

Uses gemini-embedding-2 to embed listings and user queries, then ranks by
cosine similarity.
"""

import json
import os
import base64
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional
import numpy as np
from google import genai
from google.genai import types


# Cache directory for embeddings
EMBEDDINGS_CACHE_DIR = Path("embeddings_cache")
EMBEDDINGS_CACHE_DIR.mkdir(exist_ok=True)


@dataclass
class ListingEmbedding:
    """A listing with its cached embedding."""
    listing_id: str
    title: str
    url: str
    city: str = ""
    image_url: Optional[str] = None
    image_urls: list = None  # All listing photos
    description: str = ""
    amenities: list = None
    embedding: list = None  # The vector
    
    def __post_init__(self):
        if self.amenities is None:
            self.amenities = []
        if self.image_urls is None:
            self.image_urls = []


@dataclass
class SearchResult:
    """A ranked search result."""
    listing_id: str
    title: str
    url: str
    city: str
    similarity_score: float
    description: str = ""
    image_url: Optional[str] = None
    image_urls: list = None


def _load_image_as_base64(image_path: str) -> str:
    """Load an image file and return base64 encoded data."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _get_image_mime_type(image_path: str) -> str:
    """Get MIME type from file extension."""
    ext = Path(image_path).suffix.lower()
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    return mime_map.get(ext, "image/jpeg")


def embed_text(text: str, client: genai.Client) -> list:
    """Embed a text string using gemini-embedding-2."""
    result = client.models.embed_content(
        model="models/gemini-embedding-2",
        contents=[text],
    )
    return result.embeddings[0].values


def embed_image(image_path: str, client: genai.Client) -> list:
    """Embed an image file using gemini-embedding-2."""
    image_data = _load_image_as_base64(image_path)
    mime_type = _get_image_mime_type(image_path)
    
    result = client.models.embed_content(
        model="models/gemini-embedding-2",
        contents=[
            types.Part.from_bytes(
                data=base64.b64decode(image_data),
                mime_type=mime_type,
            ),
        ],
    )
    return result.embeddings[0].values


def embed_multimodal(
    image_path: Optional[str] = None,
    text: Optional[str] = None,
    client: genai.Client = None,
) -> list:
    """
    Embed a combination of image and/or text using gemini-embedding-2.
    
    Args:
        image_path: Path to image file (optional)
        text: Text description (optional)
        client: Gemini client instance
        
    Returns:
        Embedding vector as list
    """
    if client is None:
        client = genai.Client()
    
    parts = []
    
    if text:
        parts.append(text)
    
    if image_path:
        image_data = _load_image_as_base64(image_path)
        mime_type = _get_image_mime_type(image_path)
        parts.append(
            types.Part.from_bytes(
                data=base64.b64decode(image_data),
                mime_type=mime_type,
            )
        )
    
    if not parts:
        raise ValueError("Must provide either text or image_path")
    
    result = client.models.embed_content(
        model="models/gemini-embedding-2",
        contents=parts,
    )
    return result.embeddings[0].values


def create_listing_embedding(
    listing: dict,
    client: genai.Client = None,
) -> ListingEmbedding:
    """
    Create an embedding for a single listing.
    
    Listing dict should have:
    - id or listing_id
    - title
    - url
    - city (optional)
    - image_url (optional)
    - description (optional)
    - amenities (optional list)
    
    Returns:
        ListingEmbedding with cached vector
    """
    if client is None:
        client = genai.Client()
    
    listing_id = listing.get("id") or listing.get("listing_id") or listing.get("url")
    title = listing.get("title", "")
    url = listing.get("url", "")
    city = listing.get("city", "")
    image_url = listing.get("image_url", "")
    image_urls = listing.get("image_urls", [])
    description = listing.get("description", "")
    amenities = listing.get("amenities", [])
    
    # Build text for embedding: title + description + amenities
    text_parts = [title]
    if description:
        text_parts.append(description)
    if amenities:
        text_parts.append(", ".join(amenities))
    if city:
        text_parts.append(f"Location: {city}")
    
    text_to_embed = "\n".join(text_parts)
    
    # Create embedding (text only for now, can add images later)
    embedding_vector = embed_text(text_to_embed, client)
    
    listing_embedding = ListingEmbedding(
        listing_id=listing_id,
        title=title,
        url=url,
        city=city,
        image_url=image_url,
        image_urls=image_urls,
        description=description,
        amenities=amenities,
        embedding=embedding_vector,
    )
    
    return listing_embedding


def cache_listing_embeddings(embeddings: list[ListingEmbedding]) -> None:
    """Save embeddings to disk cache."""
    cache_file = EMBEDDINGS_CACHE_DIR / "listings.jsonl"
    
    with open(cache_file, "a") as f:
        for embedding in embeddings:
            data = asdict(embedding)
            f.write(json.dumps(data) + "\n")


def load_cached_embeddings() -> dict[str, ListingEmbedding]:
    """Load cached embeddings from disk."""
    cache_file = EMBEDDINGS_CACHE_DIR / "listings.jsonl"
    embeddings = {}
    
    if not cache_file.exists():
        return embeddings
    
    with open(cache_file, "r") as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                listing_id = data["listing_id"]
                data["embedding"] = data["embedding"]  # Keep as list
                embedding = ListingEmbedding(**data)
                embeddings[listing_id] = embedding
    
    return embeddings


def cosine_similarity(vec1: list, vec2: list) -> float:
    """Compute cosine similarity between two vectors."""
    v1 = np.array(vec1)
    v2 = np.array(vec2)
    
    dot_product = np.dot(v1, v2)
    norm_v1 = np.linalg.norm(v1)
    norm_v2 = np.linalg.norm(v2)
    
    if norm_v1 == 0 or norm_v2 == 0:
        return 0.0
    
    return float(dot_product / (norm_v1 * norm_v2))


def search_listings(
    query_text: Optional[str] = None,
    query_image_path: Optional[str] = None,
    city: Optional[str] = None,
    top_k: int = 10,
    client: genai.Client = None,
) -> list[SearchResult]:
    """
    Search listings by embedding similarity.
    
    Args:
        query_text: Text description of what to search for
        query_image_path: Path to image to search with
        city: Optional city filter (case-insensitive)
        top_k: Number of results to return
        client: Gemini client instance
        
    Returns:
        Ranked list of SearchResult objects
    """
    if client is None:
        client = genai.Client()
    
    if not query_text and not query_image_path:
        raise ValueError("Must provide either query_text or query_image_path")
    
    # Embed the query
    query_embedding = embed_multimodal(
        image_path=query_image_path,
        text=query_text,
        client=client,
    )
    
    # Load cached listing embeddings
    cached_embeddings = load_cached_embeddings()
    
    if not cached_embeddings:
        raise ValueError("No cached listing embeddings. Run indexing first.")
    
    # Score all listings
    scores = []
    for listing_id, listing in cached_embeddings.items():
        # Filter by city if specified (only if listing has city field)
        if city and listing.city and listing.city.lower() != city.lower():
            continue
        
        similarity = cosine_similarity(query_embedding, listing.embedding)
        scores.append((listing_id, listing, similarity))
    
    # Sort by similarity descending
    scores.sort(key=lambda x: x[2], reverse=True)
    
    # Return top k as SearchResult objects
    results = []
    for listing_id, listing, similarity in scores[:top_k]:
        result = SearchResult(
            listing_id=listing.listing_id,
            title=listing.title,
            url=listing.url,
            city=listing.city,
            similarity_score=similarity,
            description=listing.description,
            image_url=listing.image_url,
            image_urls=listing.image_urls,
        )
        results.append(result)
    
    return results


def index_listings(listings: list[dict]) -> None:
    """
    Index a batch of listings by creating and caching embeddings.
    
    Args:
        listings: List of listing dicts with title, url, description, etc.
    """
    client = genai.Client()
    
    print(f"Indexing {len(listings)} listings...")
    
    batch_embeddings = []
    for i, listing in enumerate(listings):
        if i % 10 == 0:
            print(f"  Embedded {i}/{len(listings)}")
        
        embedding = create_listing_embedding(listing, client)
        batch_embeddings.append(embedding)
    
    cache_listing_embeddings(batch_embeddings)
    print(f"✓ Cached {len(batch_embeddings)} embeddings")


# Example usage
if __name__ == "__main__":
    # Example: create and search listings
    
    # Mock listings
    example_listings = [
        {
            "id": "1",
            "title": "Modern apartment with rooftop pool and gym",
            "url": "https://airbnb.com/rooms/1",
            "description": "Bright, spacious apartment with floor-to-ceiling windows, modern furniture, rooftop infinity pool, state-of-the-art gym, professional workspace",
            "amenities": ["pool", "gym", "wifi", "workspace", "modern kitchen"],
        },
        {
            "id": "2",
            "title": "Cozy studio with desk",
            "url": "https://airbnb.com/rooms/2",
            "description": "Warm, intimate studio apartment with a comfortable desk for remote work, kitchenette, local character",
            "amenities": ["desk", "wifi", "kitchenette"],
        },
        {
            "id": "3",
            "title": "Luxury penthouse with fitness suite",
            "url": "https://airbnb.com/rooms/3",
            "description": "Sleek penthouse with minimalist design, floor-to-ceiling windows, professional gym with equipment, rooftop terrace",
            "amenities": ["gym", "pool", "fitness", "minimal design", "high-end"],
        },
    ]
    
    # Index the listings
    index_listings(example_listings)
    
    # Search
    results = search_listings(
        query_text="spacious apartment with comfortable chair and good gym",
        top_k=3,
    )
    
    print("\nSearch results:")
    for r in results:
        print(f"  {r.title} (similarity: {r.similarity_score:.3f})")
        print(f"    {r.url}")
