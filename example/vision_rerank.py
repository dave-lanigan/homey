"""
Vision-based reranking for Airbnb listings using Gemini.

Uses Gemini's vision capabilities to analyze listing images and rerank
results based on visual features mentioned in the query.
"""

import re
from typing import Optional
import httpx
from google import genai
from google.genai import types


def _download_image(url: str) -> Optional[bytes]:
    """Download an image, returning bytes or None on failure."""
    try:
        response = httpx.get(url, timeout=10, follow_redirects=True)
        if response.status_code == 200:
            return response.content
    except Exception:
        pass
    return None


def _analyze_listing_images(
    query: str,
    image_urls: list[str],
    client: genai.Client,
    max_images: int = 12,
) -> tuple[float, str]:
    """
    Send multiple listing photos to Gemini in a single call and ask whether
    the listing matches the query. Returns (score_0_to_1, reason).
    """
    # Build the multimodal content: prompt + all images
    prompt = f"""You are reviewing photos from a single Airbnb listing.

The user is looking for: "{query}"

Carefully examine ALL the photos. Look for specific features the user mentioned
(e.g. a gym, pool, ping pong table, game room, specific style, etc.).

Rate how well this listing matches from 0-100 based on what you actually SEE in
the photos. If a specific requested feature (like a ping pong table) is visible,
score high. If it's clearly absent, score low.

Respond with ONLY a number 0-100 followed by a short reason.
Example: "90 - Photo shows a game room with a ping pong table"
"""

    contents = [prompt]
    loaded = 0
    for url in image_urls[:max_images]:
        data = _download_image(url)
        if data:
            contents.append(types.Part.from_bytes(data=data, mime_type="image/jpeg"))
            loaded += 1

    if loaded == 0:
        return (None, "no images could be downloaded")

    message = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=contents,
    )

    response_text = (message.text or "").strip()
    match = re.search(r"(\d{1,3})", response_text)
    if match:
        score = min(int(match.group(1)), 100) / 100.0
        return (score, response_text)
    return (None, response_text)


def rerank_with_vision_sync(
    query: str,
    results: list[dict],
    client: genai.Client = None,
    top_k: int = 10,
) -> list[dict]:
    """
    Rerank listings by analyzing ALL of each listing's photos with Gemini Vision.
    This lets the model find specific features (ping pong table, game room, etc.)
    that appear in later photos, not just the cover image.
    """
    if client is None:
        client = genai.Client()

    if not results:
        return results

    # Only analyze top 20 to save cost
    candidates = results[:20]

    # Keep listings that have at least one image
    with_images = [
        r for r in candidates
        if r.get("image_urls") or r.get("image_url")
    ]

    if not with_images:
        return results[:top_k]

    print(f"🔍 Analyzing photos for {len(with_images)} listings with vision...")

    scored = []
    for result in with_images:
        # Prefer full photo set, fall back to single cover image
        image_urls = result.get("image_urls") or []
        if not image_urls and result.get("image_url"):
            image_urls = [result["image_url"]]

        try:
            vision_score, reason = _analyze_listing_images(
                query=query,
                image_urls=image_urls,
                client=client,
            )

            if vision_score is None:
                # Vision failed, keep embedding score only
                scored.append((result, result["similarity_score"]))
                continue

            # Weight vision heavily since it's what the user asked for
            combined_score = (
                result["similarity_score"] * 0.3 +
                vision_score * 0.7
            )
            scored.append((result, combined_score))
            print(f"  {result['title'][:45]}: vision={vision_score:.0%} → {combined_score:.0%}")
            print(f"     {reason[:90]}")

        except Exception as e:
            print(f"  Error analyzing {result['title'][:45]}: {e}")
            scored.append((result, result["similarity_score"]))

    # Sort by combined score descending
    scored.sort(key=lambda x: x[1], reverse=True)
    reranked = [r[0] for r in scored]

    # Append any candidates that had no images at the end
    for r in results:
        if r not in reranked:
            reranked.append(r)

    return reranked[:top_k]

