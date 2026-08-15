"""
Airbnb visual search agent.

Parses user queries (images + text) and calls the embedding search tool
to find matching listings.
"""

from typing import Optional
from pathlib import Path
import json
from google import genai


def search_listings_tool(
    query_text: Optional[str] = None,
    query_image_path: Optional[str] = None,
    city: Optional[str] = None,
    top_k: int = 10,
) -> dict:
    """
    Search for Airbnb listings based on text and/or image query.
    
    Args:
        query_text: Text description of desired apartment
        query_image_path: Path to reference image
        city: Optional city to filter results
        top_k: Number of results to return
        
    Returns:
        Dict with ranked search results
    """
    from embedding_search import search_listings as do_search
    
    try:
        results = do_search(
            query_text=query_text,
            query_image_path=query_image_path,
            city=city,
            top_k=top_k,
        )
        
        # Convert SearchResult objects to dicts
        result_dicts = []
        for r in results:
            result_dicts.append({
                "title": r.title,
                "url": r.url,
                "city": r.city,
                "similarity_score": round(r.similarity_score, 3),
                "description": r.description,
                "image_url": r.image_url,
                "image_urls": r.image_urls or [],
            })
        
        return {
            "success": True,
            "count": len(result_dicts),
            "results": result_dicts,
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to search listings. Make sure embeddings are indexed first."
        }


class AirbnbSearchAgent:
    """Simple agent for Airbnb search using Gemini."""
    
    def __init__(self):
        self.client = genai.Client()
        self.conversation_history = []
        self.system_prompt = """You are an Airbnb search assistant that helps users find listings based on visual and textual preferences.

When a user describes what they're looking for:
1. Extract text descriptions (e.g., "spacious apartment with good desk and gym")
2. Note image references they mention
3. Identify priority features

Available tools:
- search_listings_tool: Search for properties matching the query

For results, format them nicely with the similarity score and key matching features.
Be conversational and ask clarifying questions if the query is ambiguous."""

    def search(self, user_query: str, image_path: Optional[str] = None, city: Optional[str] = None, top_k: int = 10, use_vision: bool = False) -> str:
        """
        Search for listings based on user query.
        
        Args:
            user_query: User's text description
            image_path: Optional reference image path
            city: Optional city filter
            top_k: Number of results
            use_vision: Use Gemini Vision to rerank results based on listing images
            
        Returns:
            Response with recommendations
        """
        # Call the search tool
        search_result = search_listings_tool(
            query_text=user_query,
            query_image_path=image_path,
            city=city,
            top_k=top_k * 2,  # Get 2x results for reranking
        )
        
        if not search_result["success"]:
            return f"Search failed: {search_result['message']}"
        
        # Apply vision-based reranking if requested
        results = search_result["results"]
        if use_vision and results:
            from vision_rerank import rerank_with_vision_sync
            results = rerank_with_vision_sync(
                query=user_query,
                results=results,
                top_k=top_k,
            )
        
        # Format results nicely
        if not results:
            city_filter = f" in {city}" if city else ""
            return f"No listings found matching your criteria{city_filter}. Try different keywords or check that embeddings are indexed."
        
        response = f"Found {len(results)} matching listings:\n\n"
        
        for i, r in enumerate(results[:top_k], 1):
            response += f"{i}. **{r['title']}**"
            if r.get('city'):
                response += f" ({r['city']})"
            response += "\n"
            response += f"   Match score: {r['similarity_score']:.1%}\n"
            if r.get('description'):
                response += f"   {r['description']}\n"
            response += f"   [View on Airbnb]({r['url']})\n\n"
        
        return response


def search_for_airbnb_sync(user_query: str, image_path: Optional[str] = None, city: Optional[str] = None, top_k: int = 10, use_vision: bool = False) -> str:
    """
    Search for Airbnb listings (synchronous interface).
    
    Args:
        user_query: Text description of what the user wants
        image_path: Optional path to reference image
        city: Optional city filter
        top_k: Number of results to return
        use_vision: Use Gemini Vision to rerank results by analyzing listing images
        
    Returns:
        Formatted response with matching listings
    """
    agent = AirbnbSearchAgent()
    return agent.search(user_query, image_path, city, top_k, use_vision)


if __name__ == "__main__":
    # Example usage
    response = search_for_airbnb_sync(
        "spacious apartment with a comfortable desk to work from and a good gym",
        top_k=5,
    )
    print(response)
