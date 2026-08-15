"""
Semantic Airbnb search agent tool.

Composes the existing filter/scrape search with embedding search and optional
vision reranking, adapted from the ``example/agent.py`` AirbnbSearchAgent:

1. Filter search (``api.tools.filter.run_search``) scrapes candidate listings
   using the structured form config (location, dates, budget, ...).
2. Multimodal embedding search (``api.tools.embedding_search``) ranks those
   listings against the user's description and optional reference image. The
   listings are cached with their vectors in Turso via SQLModel.
3. Optional vision reranking (``api.tools.vision_rerank``) scores each listing's
   photos with Gemini Vision when ``use_vision`` is enabled.
4. Structured results are handed to the chat UI for display in a listing modal.
"""

import asyncio

from pydantic_ai import ModelRetry, RunContext, Tool

from api.tools.embedding_search import SearchResult, index_listings, search_listings
from api.tools.filter import AirbnbFilters, DEFAULT_TOP_K, run_search
from api.tools.vision_rerank import rerank_with_vision_async

# Fetch 2x the requested results so there is headroom for reranking.
RERANK_MULTIPLIER = 2


def _format_results(results: list[SearchResult], top_k: int, city: str | None) -> str:
    """Format ranked results as markdown: title, city, match %, description, URL."""
    if not results:
        city_filter = f" in {city}" if city else ""
        return (
            f"No listings found matching your criteria{city_filter}. "
            "Try different keywords or adjust the search filters."
        )

    lines = [f"Found {len(results)} matching listings:", ""]
    for i, r in enumerate(results[:top_k], 1):
        name = f"{i}. **{r.title or 'Untitled listing'}**"
        if r.city:
            name += f" ({r.city})"
        lines.append(name)
        meta = [f"Match: {r.similarity_score:.0%}"]
        if r.price is not None:
            meta.append(f"${r.price:,.0f}/night")
        lines.append("   " + " · ".join(meta))
        if r.description:
            lines.append(f"   {r.description}")
        lines.append(f"   [View on Airbnb]({r.url})")
        lines.append("")
    return "\n".join(lines).rstrip()


async def smart_search_listings(
    ctx: RunContext[AirbnbFilters],
    query: str,
    use_vision: bool = False,
) -> str:
    """
    Search Airbnb for listings matching the user's description and attached
    reference image, ranked by semantic similarity (and optionally by analyzing
    the listing photos).

    This runs the filter search configured in the search form (location, dates,
    budget, amenities, keywords), then ranks the results against ``query`` using
    embedding similarity. Enable ``use_vision`` when the user cares about features
    that are only visible in photos (e.g. "ping pong table", "game room", "modern
    decor").

    Args:
        query: The user's free-text description of what they want (features, style,
            vibe). Pass the user's request as-is.
        use_vision: When True, analyze each listing's photos with Gemini Vision to
            score how well they visually match the query. Slower and costs more.

    Returns:
        A short summary. Structured listing data is sent separately to the UI.
    """
    print("running smart_search_listings")
    params = ctx.deps

    if not params.has_required():
        missing = [n for n in ("location", "checkin", "nights") if getattr(params, n) is None]
        raise ModelRetry(
            "Cannot search yet — missing " + ", ".join(missing) + ". "
            "Ask the user to provide their destination, check-in date and number of "
            "nights (or fill them in the search form) before calling this tool again."
        )

    top_k = max(1, params.top_k or DEFAULT_TOP_K)
    use_vision = use_vision or params.use_vision
    query = (query or "").strip()
    if not query and params.keywords:
        query = ", ".join(params.keywords)

    try:
        # Step 1: scrape candidate listings via the existing filter search. Full
        # photo galleries are only harvested when the vision step will use them.
        response = await run_search(
            params,
            progress=params.report_progress,
            harvest_photos=bool(use_vision or params._query_image),
        )
        if not response.listings:
            return _format_results([], top_k, params.location)

        # Step 2: cache listings + embeddings in SQLite (new URLs are embedded).
        await params.report_progress("Indexing listings")
        listings_data = [l.model_dump() for l in response.listings]
        new_embeddings = await asyncio.to_thread(index_listings, listings_data)
        print(f"   🧠 Indexed {new_embeddings} new embeddings ({len(listings_data)} listings cached)")

        # Step 3: multimodal embedding search — combine the description with the
        # user's reference image when one was attached to this chat turn.
        await params.report_progress(
            "Comparing your image and description"
            if params._query_image
            else "Performing semantic search"
        )
        current_urls = {l["url"] for l in listings_data if l.get("url")}
        results = await asyncio.to_thread(
            search_listings,
            query_text=query,
            query_image_data=params._query_image,
            query_image_media_type=params._query_image_media_type,
            city=params.location,
            top_k=top_k * RERANK_MULTIPLIER,
            urls=current_urls,
        )

        # Step 4: compare listing photos directly with the reference image. Text-only
        # searches can opt into the same photo analysis with use_vision.
        if (use_vision or params._query_image) and results:
            await params.report_progress(
                "Comparing listing photos to your image"
                if params._query_image
                else "Analyzing listing photos"
            )
            results = await rerank_with_vision_async(
                query,
                results,
                top_k=top_k,
                reference_image_data=params._query_image,
                reference_image_media_type=params._query_image_media_type,
            )
        else:
            results = results[:top_k]

        # Step 5: expose structured cards to the chat stream. Keep the tool return
        # short so the model does not duplicate listings as markdown.
        params._listing_results = [
            {
                "title": result.title or "Untitled listing",
                "url": result.url,
                "city": result.city,
                "price": result.price,
                "rating": result.rating,
                "description": result.description,
                "image_url": result.image_url,
                "image_urls": result.image_urls,
                "amenities": result.amenities,
                "house_rules": result.house_rules,
                "match_score": result.similarity_score,
                "vision_score": result.vision_score,
            }
            for result in results[:top_k]
        ]
        if not params._listing_results:
            return _format_results([], top_k, params.location)
        return (
            f"Found {len(params._listing_results)} matching listings. "
            "They are available in the interactive results viewer."
        )

    except ValueError as e:
        raise ModelRetry(f"Search failed: {e}")
    except Exception as e:
        return (
            f"Search failed: {e}. Make sure the location, check-in date and nights "
            "are configured, then try again."
        )


smart_search_listings_tool = Tool(smart_search_listings)
