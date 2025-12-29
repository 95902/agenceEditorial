"""FastAPI main application."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from python_scripts.api.middleware.rate_limit import setup_rate_limiting
from python_scripts.api.routers import (
    article_enrichment,
    article_generation,
    article_training,
    competitors,
    discovery,
    draft,
    errors,
    executions,
    health,
    images,
    sites,
    trend_pipeline,
)
from python_scripts.config.settings import settings
from python_scripts.utils.logging import setup_logging

# Setup logging
setup_logging()

# Create FastAPI app
app = FastAPI(
    title="Agent Éditorial & Concurrentiel API",
    version="1.0.0",
    description="API REST pour le système d'analyse éditoriale et concurrentielle multi-agents",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup rate limiting
setup_rate_limiting(app)

# Register routers
app.include_router(health.router, prefix="/api/v1")
app.include_router(sites.router, prefix="/api/v1")
app.include_router(competitors.router, prefix="/api/v1")
app.include_router(discovery.router, prefix="/api/v1")
app.include_router(trend_pipeline.router, prefix="/api/v1")
app.include_router(executions.router, prefix="/api/v1")
app.include_router(errors.router, prefix="/api/v1")
app.include_router(article_enrichment.router, prefix="/api/v1")
app.include_router(article_generation.router, prefix="/api/v1")
app.include_router(article_training.router, prefix="/api/v1")
app.include_router(draft.router, prefix="/api/v1")
app.include_router(images.router, prefix="/api/v1")

# Mount static files for serving generated images
# This allows accessing images via /outputs/articles/images/...
article_images_dir = Path(settings.article_images_dir)
if article_images_dir.exists():
    app.mount(
        "/outputs/articles/images",
        StaticFiles(directory=str(article_images_dir)),
        name="article_images",
    )


@app.on_event("startup")
async def startup_event() -> None:
    """Startup event handler."""
    pass


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Shutdown event handler."""
    pass

