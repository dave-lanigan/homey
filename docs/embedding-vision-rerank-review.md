# Embedding & Vision Rerank — Review and Implementation Plan

Review of the semantic search pipeline in Homey, focused on the embedding and
vision-reranking stages. Use this as a checklist when implementing improvements.

## Pipeline (as implemented)

From `smart_search_listings` in [api/tools/agent_search.py](../api/tools/agent_search.py):

1. **Filter/scrape** — `run_search(params)` scrapes candidates from the form config.
2. **Index** — `index_listings` upserts rows and embeds *new* URLs into SQLite.
3. **Embedding search** — `search_listings` embeds the query, cosine-ranks, returns `top_k * 2`.
4. **Vision rerank** (optional) — `rerank_with_vision_async` re-scores photos, else truncate to `top_k`.
5. **Format** as markdown.

Verdict: the "retrieve-then-rerank" architecture is correct (recall via embeddings →
precise rerank via a vision LLM is a standard, good pattern). The gaps are in execution.

---

## Embedding stage — issues

### 1. No query/document `task_type` asymmetry (highest priority) [Added]
`embed_text` / `embed_multimodal` embed listings and the query identically.
Gemini embedding models support `task_type`; symmetric embedding hurts retrieval quality.

- Documents (listings): `RETRIEVAL_DOCUMENT`
- Query: `RETRIEVAL_QUERY`

```python
# documents
config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT")
# query
config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY")
```

### 2. "Multimodal" is a misnomer
`embed_multimodal` is called with `image_path=None`, so recall is purely text-based over
`build_listing_text` (title + city + description + amenities + `full_text[:3000]`).
Valid design (text recall + vision rerank), but the naming implies image embeddings that
never happen. Rename or actually use images.

### 3. Per-listing embedding calls
`index_listings` makes one API call per listing. `embed_content` accepts batches — batch to
cut latency and cost.

### 4. Brute-force cosine every query
`search_listings` loads all listings + vectors from SQLite and does pure-Python cosine over
the full set on every call. Fine for small N; O(N·D) in Python won't scale. Consider a vector
index (sqlite-vec / FAISS) or at least numpy vectorization.

### 5. Risky city filter
Exact match `listing["city"].lower() == params.location.lower()`. `params.location` is often
`"Lima, Peru"` while scraped `city` may differ, silently dropping all results. It's also
redundant because the run is already scoped by `current_urls`. Drop the city filter here and
rely on the URL scope.

---

## Vision rerank — issues

From `rerank_with_vision_sync` in [api/tools/vision_rerank.py](../api/tools/vision_rerank.py):

### 1. Scale-mismatched score fusion
`combined = similarity * 0.3 + vision * 0.7`. Raw cosine sits in a narrow high band
(~0.6–0.85) while vision spans a true 0–1, so the 0.3 term is nearly a constant offset and
barely reorders. Fix: min-max normalize embedding scores across candidates before blending,
or make vision the primary sort with embedding as a tiebreaker.

### 2. Fragile score parsing
`re.search(r"(\d{1,3})", response_text)` grabs the first number anywhere in the reply. Any
deviation from "number first" yields a wrong score. Use structured output
(`response_mime_type="application/json"` + a schema) instead of regex-scraping free text.

### 3. Sequential, blocking I/O
Listings are processed one at a time; within each, up to 12 images download serially via
blocking `httpx.get`, all in a single worker thread. Parallelize downloads and run listing
analyses concurrently (`asyncio.gather` / async client).

### 4. Hardcoded MIME type
Every image is sent as `image/jpeg` regardless of actual format (png/webp). Detect the real
MIME type.

### 5. No vision-score caching
Vision scores aren't persisted, so identical queries re-pay the full vision cost. Embeddings
are cached; vision isn't. Cache per (query, listing) or persist last vision score.

### 6. Funnel cutoff sensitivity
`candidates = results[:20]` — a true match ranked >20 by embedding never reaches vision.
Reasonable in principle, but weakened by the symmetric-embedding issue above.

---

## Implementation priority

Quality-affecting (do first):
1. Add `task_type` document/query asymmetry.
2. Fix score fusion — normalize embedding scores before blending, or make vision primary.
3. Replace regex score parsing with structured JSON output.

Performance / robustness (do next):
4. Parallelize image downloads + listing analyses.
5. Drop or fix the exact-match city filter.
6. Batch the embedding calls.
7. Cache vision scores.
8. Detect real image MIME types.
