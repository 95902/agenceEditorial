# Research & Technical Decisions: Agent Éditorial & Concurrentiel

**Date**: 2025-01-25  
**Plan**: [plan.md](./plan.md)

This document consolidates research findings and technical decisions for all areas requiring clarification or best practice patterns.

---

## 1. LangChain 0.2+ / LangGraph Integration Patterns

### Decision
Use **LangChain 0.2+ with LangGraph** for multi-agent orchestration, implementing a state machine pattern where agents communicate via shared state in PostgreSQL and coordinate through the orchestrator agent.

### Rationale
- LangGraph provides explicit state machine definition with visual representation
- Native support for conditional branching and agent coordination
- Integrates seamlessly with LangChain's existing tool ecosystem
- Supports async execution compatible with FastAPI background tasks
- State persistence in PostgreSQL aligns with observability requirements

### Alternatives Considered
- **Pure LangChain Agents**: Too implicit, harder to debug and trace
- **Custom orchestration with asyncio**: More control but significant development overhead
- **Prefect/Dagster**: Overkill for this use case, adds unnecessary complexity

### Implementation Patterns

**State Machine Structure:**
```python
from langgraph.graph import StateGraph
from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages

class WorkflowState(TypedDict):
    execution_id: str
    domain: str
    current_step: str
    site_profile: dict | None
    competitors: list[str]
    articles: list[dict]
    topics: dict | None
    errors: list[str]

# Create graph
workflow = StateGraph(WorkflowState)

# Add nodes (agents)
workflow.add_node("crawl", agent_crawl.execute)
workflow.add_node("analyze", agent_analysis.execute)
workflow.add_node("find_competitors", agent_competitor.execute)
# ... more agents

# Define edges
workflow.set_entry_point("crawl")
workflow.add_edge("crawl", "analyze")
workflow.add_conditional_edges(
    "analyze",
    should_continue,  # Function that decides next step
    {"find_competitors": "find_competitors", "end": END}
)
```

**Integration with FastAPI:**
- Run LangGraph in background task: `background_tasks.add_task(run_workflow, execution_id, domain)`
- Save state transitions to `workflow_executions` table for observability
- Use PostgreSQL state store for persistence between background task restarts

---

## 2. Crawl4AI Async Best Practices

### Decision
Use **Crawl4AI 0.7+ with async context managers** and custom wrapper functions that handle robots.txt parsing, rate limiting, and crawl-delay enforcement before initiating crawls.

### Rationale
- Crawl4AI 0.7+ has improved async support
- Module-based approach (not container) keeps Python ecosystem consistent
- Playwright integration for JavaScript rendering is well-supported
- Async patterns align with constitutional requirement (all I/O async)

### Alternatives Considered
- **Scrapy**: More mature but heavier, less flexible for dynamic content
- **BeautifulSoup + httpx**: Requires manual JavaScript rendering setup
- **Selenium**: Too heavy, slower, browser overhead unnecessary

### Implementation Patterns

**Async Crawler Wrapper:**
```python
from crawl4ai import AsyncWebCrawler
from ingestion.robots_txt import RobotsTxtParser
import asyncio

async def crawl_with_permissions(
    domain: str,
    urls: list[str],
    db: AsyncSession
) -> list[dict]:
    """Crawl URLs respecting robots.txt and crawl-delay."""
    # Fetch and parse robots.txt (cached in scraping_permissions table)
    permissions = await get_scraping_permissions(db, domain)
    
    if not permissions.scraping_allowed:
        raise CrawlingError(f"Scraping disallowed for {domain}")
    
    delay = permissions.crawl_delay or 2  # Default 2 seconds
    
    results = []
    async with AsyncWebCrawler(
        headless=True,
        browser_type="chromium",
        # Use Playwright for JS rendering
    ) as crawler:
        for url in urls:
            # Check if URL is disallowed
            if is_url_disallowed(url, permissions.disallowed_paths):
                continue
            
            result = await crawler.arun(url=url)
            results.append({
                "url": url,
                "content": result.cleaned_html,
                "text": result.markdown,
                "metadata": result.metadata
            })
            
            # Enforce crawl-delay
            await asyncio.sleep(delay)
    
    return results
```

**Robots.txt Caching:**
- Store parsed robots.txt in `scraping_permissions` table
- Cache TTL: 24 hours
- Refresh on cache miss or TTL expiration
- Store `disallowed_paths`, `crawl_delay`, `user_agent` requirements

---

## 3. BERTopic 0.16+ Configuration & Performance

### Decision
Use **BERTopic 0.16+ with Sentence-Transformers embeddings** (all-MiniLM-L6-v2 for balance of speed/quality), UMAP for dimensionality reduction, and HDBSCAN for clustering. Configure with `min_topic_size=10` and `nr_topics="auto"` for automatic topic discovery.

### Rationale
- BERTopic provides excellent topic modeling with minimal hyperparameter tuning
- Automatic topic discovery (`nr_topics="auto"`) adapts to data characteristics
- Temporal topic evolution built-in (important for trend detection)
- Visualization generation is straightforward
- Works well on CPU (GPU optional for large datasets)

### Alternatives Considered
- **LDA (Latent Dirichlet Allocation)**: Bag-of-words limitation, requires fixed topic count
- **NMF (Non-negative Matrix Factorization)**: Similar limitations to LDA
- **Top2Vec**: Simpler but less flexible, no hierarchical clustering

### Implementation Patterns

**BERTopic Pipeline:**
```python
from bertopic import BERTopic
from sentence_transformers import SentenceTransformer
from umap import UMAP
from hdbscan import HDBSCAN

# Initialize embedding model
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

# Initialize BERTopic with components
topic_model = BERTopic(
    embedding_model=embedding_model,
    umap_model=UMAP(
        n_neighbors=15,
        n_components=5,
        min_dist=0.0,
        metric="cosine"
    ),
    hdbscan_model=HDBSCAN(
        min_cluster_size=10,  # Minimum 10 articles per topic
        min_samples=5,
        metric="euclidean",
        cluster_selection_method="eom"
    ),
    min_topic_size=10,
    nr_topics="auto",  # Automatic topic discovery
    calculate_probabilities=True,
    verbose=True
)

# Fit on article texts
topics, probs = topic_model.fit_transform(article_texts)

# Get topic info
topic_info = topic_model.get_topic_info()

# Generate visualizations (save to /mnt/user-data/outputs/visualizations/)
topic_model.visualize_topics().write_html("visualizations/topics_2d.html")
topic_model.visualize_barchart().write_html("visualizations/topics_barchart.html")
```

**Integration with Qdrant:**
- Use same embedding model (all-MiniLM-L6-v2) for consistency
- Store topic assignments in `competitor_articles` table (topic_id column)
- Store topic metadata in `bertopic_analysis` table (JSONB)
- Link articles to topics via embeddings similarity if needed

---

## 4. Qdrant Integration Patterns

### Decision
Use **Qdrant with single collection architecture** for MVP (single-tenant). Use Sentence-Transformers for embeddings generation, store rich payloads with metadata, and implement deduplication via cosine similarity threshold (0.92).

### Rationale
- Qdrant is performant and well-integrated with Python ecosystem
- Single collection simplifies architecture (can split later if needed)
- Rich payloads enable filtering without re-querying PostgreSQL
- Similarity-based deduplication more accurate than exact hash matching

### Alternatives Considered
- **Pinecone**: Cloud-only, adds cost and dependency
- **Weaviate**: More complex setup, overkill for MVP
- **FAISS (local)**: No persistence, requires manual vector storage

### Implementation Patterns

**Collection Setup:**
```python
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

client = QdrantClient(url="http://localhost:6333")

# Create collection (single for MVP)
client.create_collection(
    collection_name="competitor_articles",
    vectors_config=VectorParams(
        size=384,  # all-MiniLM-L6-v2 dimension
        distance=Distance.COSINE
    )
)

# Upsert with payload
points = [
    PointStruct(
        id=article_id,
        vector=embedding,
        payload={
            "domain": article.domain,
            "title": article.title,
            "published_date": article.published_date.isoformat(),
            "keywords": article.keywords,
            "topic_id": article.topic_id,
            "text_hash": article.text_hash  # For deduplication check
        }
    )
    for article_id, embedding, article in articles
]

client.upsert(collection_name="competitor_articles", points=points)
```

**Deduplication Strategy:**
```python
# Before inserting, check for similar content
search_results = client.search(
    collection_name="competitor_articles",
    query_vector=new_embedding,
    limit=1,
    score_threshold=0.92
)

if search_results and search_results[0].score > 0.92:
    # Mark as duplicate, don't insert
    article.is_duplicate = True
    article.duplicate_of = search_results[0].id
else:
    # Insert new article
    await insert_article(db, article)
    await index_in_qdrant(article, embedding)
```

---

## 5. FastAPI Background Tasks & WebSocket

### Decision
Use **FastAPI BackgroundTasks** for workflow execution with **WebSocket support** for real-time progress streaming. Store workflow state in PostgreSQL, emit progress events via WebSocket, and use asyncio.Event for coordination.

### Rationale
- FastAPI BackgroundTasks are simple and sufficient for MVP
- WebSocket provides better UX than polling
- PostgreSQL state ensures durability if background task crashes
- Async-compatible with existing stack

### Alternatives Considered
- **Celery**: Adds Redis dependency, overkill for single-server MVP
- **RQ (Redis Queue)**: Requires Redis, similar overhead
- **Polling only**: Simpler but worse UX, more API load

### Implementation Patterns

**Background Task with Progress:**
```python
from fastapi import BackgroundTasks, WebSocket
from database.models import WorkflowExecution

async def run_analysis_workflow(
    execution_id: str,
    domain: str,
    max_pages: int,
    progress_callback: callable | None = None
):
    """Execute workflow with progress updates."""
    execution = await get_execution(db, execution_id)
    
    try:
        # Update status
        await update_execution_status(execution_id, "running")
        
        # Step 1: Crawl
        if progress_callback:
            await progress_callback({
                "step": "crawling",
                "progress": 10,
                "message": f"Crawling {domain}..."
            })
        pages = await crawl_domain(domain, max_pages)
        
        # Step 2: Analyze
        if progress_callback:
            await progress_callback({
                "step": "analyzing",
                "progress": 50,
                "message": "Analyzing editorial style..."
            })
        profile = await analyze_editorial_style(pages)
        
        # ... more steps
        
        await update_execution_status(execution_id, "completed", result=profile)
        
    except Exception as e:
        await update_execution_status(execution_id, "failed", error=str(e))
        raise

# In router
@router.post("/sites/analyze", status_code=202)
async def analyze_site(
    request: SiteAnalysisRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    execution = await create_workflow_execution(db, "editorial_analysis")
    
    background_tasks.add_task(
        run_analysis_workflow,
        execution.execution_id,
        request.domain,
        request.max_pages
    )
    
    return ExecutionResponse(execution_id=execution.execution_id, ...)

# WebSocket endpoint
@router.websocket("/executions/{execution_id}/stream")
async def stream_progress(websocket: WebSocket, execution_id: str):
    await websocket.accept()
    
    async def progress_callback(progress_data: dict):
        await websocket.send_json(progress_data)
    
    # Monitor execution and send updates
    execution = await get_execution(db, execution_id)
    while execution.status == "running":
        # Poll for updates or use async event
        updates = await get_execution_updates(execution_id)
        if updates:
            await websocket.send_json(updates)
        await asyncio.sleep(1)
    
    await websocket.close()
```

---

## 6. PostgreSQL Async Patterns (SQLAlchemy 2.0)

### Decision
Use **SQLAlchemy 2.0 async patterns** with async engine, async sessionmaker, and explicit async context managers. Use connection pooling optimized for async, and ensure all database operations are properly awaited.

### Rationale
- SQLAlchemy 2.0 async is mature and well-documented
- Native async support eliminates sync/async bridges
- Connection pooling essential for performance
- Aligns with constitutional requirement (all I/O async)

### Alternatives Considered
- **Tortoise ORM**: Good async support but smaller ecosystem
- **Databases (encode)**: Lower-level, more boilerplate
- **SQLAlchemy 1.4 async**: Deprecated in favor of 2.0

### Implementation Patterns

**Session Management:**
```python
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker
)
from sqlalchemy.orm import declarative_base

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,  # Verify connections
    echo=False  # Set True for SQL debugging
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

# Dependency for FastAPI
async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

# Usage in routes
@router.get("/sites/{domain}")
async def get_site(
    domain: str,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(SiteProfile).where(SiteProfile.domain == domain)
    )
    profile = result.scalars().first()
    return profile
```

**Transaction Patterns:**
```python
# Explicit transaction
async with AsyncSessionLocal() as session:
    async with session.begin():
        profile = SiteProfile(domain=domain, ...)
        session.add(profile)
        # No explicit commit needed, begin() handles it
```

---

## 7. Data Purge Strategy (90-day retention)

### Decision
Use **APScheduler** for scheduled jobs running daily at 2 AM UTC. Implement cascade deletion: delete from Qdrant first (by article IDs), then delete from PostgreSQL (with proper foreign key handling), and log all purge operations in `audit_log`.

### Rationale
- APScheduler integrates well with FastAPI/async Python
- Daily batch deletion more efficient than per-request checks
- Cascade deletion prevents orphaned data
- Audit logging essential for compliance

### Alternatives Considered
- **Cron jobs**: Less integrated, harder to manage in containerized environments
- **Database triggers**: Possible but less flexible, harder to log
- **Manual cleanup**: Not suitable for production

### Implementation Patterns

**Scheduled Purge Job:**
```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta

async def purge_old_data(db: AsyncSession, qdrant_client: QdrantClient):
    """Purge articles older than 90 days."""
    cutoff_date = datetime.utcnow() - timedelta(days=90)
    
    # Find articles to purge
    result = await db.execute(
        select(CompetitorArticle)
        .where(CompetitorArticle.published_date < cutoff_date)
    )
    articles_to_purge = result.scalars().all()
    
    if not articles_to_purge:
        return
    
    article_ids = [article.id for article in articles_to_purge]
    
    # 1. Delete from Qdrant
    qdrant_client.delete(
        collection_name="competitor_articles",
        points_selector=PointIdsList(points=article_ids)
    )
    
    # 2. Delete from PostgreSQL (cascade will handle related data)
    await db.execute(
        delete(CompetitorArticle)
        .where(CompetitorArticle.id.in_(article_ids))
    )
    
    # 3. Log purge operation
    audit_log = AuditLog(
        action="purge_old_data",
        details={
            "article_count": len(article_ids),
            "cutoff_date": cutoff_date.isoformat(),
            "article_ids": article_ids[:100]  # First 100 for log
        },
        timestamp=datetime.utcnow()
    )
    db.add(audit_log)
    await db.commit()

# Setup scheduler
scheduler = AsyncIOScheduler()
scheduler.add_job(
    purge_old_data,
    trigger=CronTrigger(hour=2, minute=0),  # 2 AM UTC daily
    args=[db, qdrant_client]
)
scheduler.start()
```

---

## 8. Rate Limiting Implementation (IP-based)

### Decision
Use **slowapi** (FastAPI-compatible rate limiter) with in-memory storage for MVP. Configure per-endpoint limits: 100 req/min for general endpoints, 10 req/min for analysis endpoints (more resource-intensive).

### Rationale
- slowapi is lightweight and FastAPI-native
- In-memory sufficient for single-server MVP
- Easy to migrate to Redis later if needed
- Per-endpoint configuration provides flexibility

### Alternatives Considered
- **Redis-based rate limiting**: More robust but adds dependency
- **Custom middleware**: More control but significant development effort
- **Cloud provider rate limiting**: Adds vendor lock-in

### Implementation Patterns

**Rate Limiting Setup:**
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Initialize limiter
limiter = Limiter(key_func=get_remote_address)

# Add to FastAPI app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Apply to routes
@router.post("/sites/analyze")
@limiter.limit("10/minute")  # Stricter limit for heavy operations
async def analyze_site(request: Request, ...):
    ...

@router.get("/sites/{domain}")
@limiter.limit("100/minute")  # Standard limit
async def get_site(request: Request, domain: str, ...):
    ...

# Middleware for global rate limiting
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # Global rate limit check
    return await call_next(request)
```

**Testing Rate Limiting:**
```python
import pytest
from fastapi.testclient import TestClient

def test_rate_limiting(client: TestClient):
    # Make requests exceeding limit
    for _ in range(11):
        response = client.post("/api/v1/sites/analyze", json={...})
    
    assert response.status_code == 429
    assert "Retry-After" in response.headers
```

---

## Summary of Key Decisions

| Area | Decision | Key Rationale |
|------|----------|---------------|
| Agent Orchestration | LangGraph state machine | Explicit control flow, better observability |
| Web Crawling | Crawl4AI async with robots.txt | Ethical scraping, async compatibility |
| Topic Modeling | BERTopic with auto-discovery | Minimal tuning, temporal evolution support |
| Vector Store | Qdrant single collection | Performance, Python integration |
| Background Tasks | FastAPI BackgroundTasks + WebSocket | Simplicity, real-time updates |
| Database | SQLAlchemy 2.0 async | Mature async patterns |
| Data Retention | APScheduler daily purge | Compliance, efficient batch operations |
| Rate Limiting | slowapi in-memory | Lightweight, easy migration path |

---

**Status**: ✅ **RESEARCH COMPLETE**  
**Next**: Proceed to Phase 1 (Data Model, API Contracts, Quickstart)