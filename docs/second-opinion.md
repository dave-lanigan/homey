# Airbnb Chatbot Architecture: Current State vs. Modernized Pipeline

## 1. Current Architecture Assessment

The existing implementation provides a solid, highly capable baseline, particularly with the inclusion of a vision reranking step. It effectively implements a modern multi-stage RAG (Retrieval-Augmented Generation) pattern.

**Current Pipeline:**

1. **Filter/scrape** — `run_search(params)` scrapes candidates from the form config.

2. **Index** — `index_listings` upserts rows and embeds *new* URLs into SQLite.

3. **Embedding search** — `search_listings` embeds the query, cosine-ranks, returns `top_k * 2`.

4. **Vision rerank** (optional) — `rerank_with_vision_async` re-scores photos, else truncate to `top_k`.

5. **Format** — Outputs as markdown.

However, if the goal is the "best possible" architecture based on state-of-the-art modern tech, there are several key areas to optimize for **latency, cost, and retrieval accuracy**.

---

## 2. Areas for Modernization

### A. Database & Indexing (Moving Beyond SQLite)

* **Current State:** Scraping candidates and upserting/embedding into SQLite.

* **Modern Upgrade - Vector DBs & Hybrid Search:** SQLite (with `sqlite-vss` or `sqlite-vec`) is excellent for local development. However, for production scale, migrating to **PostgreSQL with** `pgvector` or a dedicated vector database (like Qdrant, Pinecone, or Milvus) is recommended.

* **Crucial Addition:** You need **Hybrid Search**. Pure embedding search is notoriously bad at exact keyword matches (e.g., finding a specific neighborhood name or "WiFi"). Modern architectures combine Dense Vector Search (embeddings) with Sparse Keyword Search (BM25) and use an algorithm like Reciprocal Rank Fusion (RRF) to merge the results.

### B. Embedding Search (Multimodal Capabilities)

* **Current State:** Embed text query, cosine-rank, return `top_k * 2`.

* **Modern Upgrade - Multimodal Embeddings:** Modern tech allows you to embed *images and text into the exact same vector space* using models like **CLIP**, **SigLIP**, or Google's Multimodal Embeddings. If you pre-calculate the image embeddings, a user can
