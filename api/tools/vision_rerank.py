"""
Vision-based reranking for Airbnb listings using Gemini.

Uses Gemini's vision capabilities to analyze listing images and rerank
results based on visual features mentioned in the query.
"""

import asyncio
import os
import re
from typing import Optional

import httpx
from dotenv import load_dotenv
from google import genai
from google.genai import types

from api.tools.embedding_search import SearchResult

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../../.env"))

VISION_MODEL = os.getenv("GEMINI_VISION_MODEL", "gemini-2.5-flash")
VISION_CONCURRENCY = max(1, int(os.getenv("GEMINI_VISION_CONCURRENCY", "4")))
IMAGE_DOWNLOAD_CONCURRENCY = max(1, int(os.getenv("IMAGE_DOWNLOAD_CONCURRENCY", "12")))


def _download_image(url: str) -> Optional[bytes]:
    """Download an image, returning bytes or None on failure."""
    try:
        response = httpx.get(url, timeout=15, follow_redirects=True)
        if response.status_code == 200:
            return response.content
    except Exception:
        pass
    return None


def _analyze_listing_images(
    query: str,
    image_urls: list[str],
    client: genai.Client,
    reference_image_data: bytes | None = None,
    reference_image_media_type: str | None = None,
    max_images: int = 12,
) -> tuple[Optional[float], str]:
    """
    Send multiple listing photos to Gemini in a single call and ask whether
    the listing matches the query. Returns (score_0_to_1, reason).
    """
    prompt = f"""You are reviewing photos from a single Airbnb listing.

The user is looking for: "{query}"

Carefully examine all the listing photos. Look for specific features the user
mentioned (e.g. a gym, pool, game room, or style). If a REFERENCE IMAGE is
provided, compare its architecture, interior design, colors, materials,
atmosphere, and visible features directly with the LISTING PHOTOS.

Rate how well this listing matches from 0-100 based on what you actually SEE in
the photos. If a specific requested feature (like a ping pong table) is visible,
score high. If it's clearly absent, score low.

Respond with ONLY a number 0-100 followed by a short reason.
Example: "90 - Photo shows a game room with a ping pong table"
"""

    contents = [prompt]
    if reference_image_data:
        contents.extend(
            [
                "REFERENCE IMAGE:",
                types.Part.from_bytes(
                    data=reference_image_data,
                    mime_type=reference_image_media_type or "image/jpeg",
                ),
                "LISTING PHOTOS:",
            ]
        )
    loaded = 0
    for url in image_urls[:max_images]:
        data = _download_image(url)
        if data:
            contents.append(types.Part.from_bytes(data=data, mime_type="image/jpeg"))
            loaded += 1

    if loaded == 0:
        return (None, "no images could be downloaded")

    message = client.models.generate_content(
        model=VISION_MODEL,
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
    results: list[SearchResult],
    client: genai.Client = None,
    top_k: int = 10,
    reference_image_data: bytes | None = None,
    reference_image_media_type: str | None = None,
) -> list[SearchResult]:
    """
    Rerank listings by analyzing each listing's photos with Gemini Vision.

    The combined score weights vision (0.7) over the embedding score (0.3), so
    features visible in photos can override text-only similarity. Listings that
    fail vision analysis (or have no images) keep their embedding score and are
    appended at the end.
    """
    if client is None:
        client = genai.Client()

    if not results:
        return results

    candidates = results[:20]

    with_images = [r for r in candidates if r.image_urls or r.image_url]
    if not with_images:
        return results[:top_k]

    scored = []
    for result in with_images:
        image_urls = list(result.image_urls or [])
        if not image_urls and result.image_url:
            image_urls = [result.image_url]

        try:
            vision_score, reason = _analyze_listing_images(
                query,
                image_urls,
                client,
                reference_image_data=reference_image_data,
                reference_image_media_type=reference_image_media_type,
            )

            if vision_score is None:
                scored.append((result, result.similarity_score))
                continue

            combined = result.similarity_score * 0.3 + vision_score * 0.7
            result.vision_score = vision_score
            result.similarity_score = combined
            scored.append((result, combined))
        except Exception as e:
            scored.append((result, result.similarity_score))

    scored.sort(key=lambda x: x[1], reverse=True)
    reranked = [r[0] for r in scored]

    for r in results:
        if r not in reranked:
            reranked.append(r)

    return reranked[:top_k]


async def rerank_with_vision_async(
    query: str,
    results: list[SearchResult],
    client: genai.Client = None,
    top_k: int = 10,
    reference_image_data: bytes | None = None,
    reference_image_media_type: str | None = None,
) -> list[SearchResult]:
    """Download photos and score listings concurrently with bounded fan-out."""
    if client is None:
        client = genai.Client()
    if not results:
        return results

    candidates = results[:20]
    with_images = [r for r in candidates if r.image_urls or r.image_url]
    if not with_images:
        return results[:top_k]

    vision_semaphore = asyncio.Semaphore(VISION_CONCURRENCY)
    download_semaphore = asyncio.Semaphore(IMAGE_DOWNLOAD_CONCURRENCY)

    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as http:
        async def download(url: str) -> tuple[bytes, str] | None:
            async with download_semaphore:
                try:
                    response = await http.get(url)
                    if response.status_code == 200:
                        media_type = response.headers.get("content-type", "image/jpeg").split(";", 1)[0]
                        return response.content, media_type
                except Exception:
                    pass
                return None

        async def score_result(result: SearchResult) -> tuple[SearchResult, float]:
            image_urls = list(result.image_urls or [])
            if not image_urls and result.image_url:
                image_urls = [result.image_url]

            downloaded = await asyncio.gather(*(download(url) for url in image_urls[:12]))
            photos = [photo for photo in downloaded if photo is not None]
            if not photos:
                return result, result.similarity_score

            contents: list = [
                f"""You are reviewing photos from a single Airbnb listing.

The user is looking for: "{query}"

Compare all LISTING PHOTOS with the user's description. If a REFERENCE IMAGE is
provided, compare architecture, interior design, colors, materials, atmosphere,
and visible features directly. Respond with ONLY a score from 0-100 followed by
a short reason."""
            ]
            if reference_image_data:
                contents.extend(
                    [
                        "REFERENCE IMAGE:",
                        types.Part.from_bytes(
                            data=reference_image_data,
                            mime_type=reference_image_media_type or "image/jpeg",
                        ),
                        "LISTING PHOTOS:",
                    ]
                )
            contents.extend(
                types.Part.from_bytes(data=data, mime_type=media_type)
                for data, media_type in photos
            )

            try:
                async with vision_semaphore:
                    message = await client.aio.models.generate_content(
                        model=VISION_MODEL,
                        contents=contents,
                    )
                match = re.search(r"(\d{1,3})", (message.text or "").strip())
                if not match:
                    return result, result.similarity_score
                vision_score = min(int(match.group(1)), 100) / 100.0
                combined = result.similarity_score * 0.3 + vision_score * 0.7
                result.vision_score = vision_score
                result.similarity_score = combined
                return result, combined
            except Exception:
                return result, result.similarity_score

        scored = await asyncio.gather(*(score_result(result) for result in with_images))

    scored.sort(key=lambda item: item[1], reverse=True)
    reranked = [result for result, _ in scored]
    reranked.extend(result for result in results if result not in reranked)
    return reranked[:top_k]
