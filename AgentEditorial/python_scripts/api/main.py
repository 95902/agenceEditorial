"""FastAPI main application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from python_scripts.api.middleware.rate_limit import setup_rate_limiting
from python_scripts.api.routers import competitors, executions, health, sites
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
app.include_router(executions.router, prefix="/api/v1")


@app.on_event("startup")
async def startup_event() -> None:
    """Startup event handler."""
    pass


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Shutdown event handler."""
    pass

