"""API router for scraping endpoints (T103, T104, T108 - US5)."""

import time
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.api.dependencies import get_db_session as get_db
from python_scripts.api.schemas.requests import ScrapingRequest
from python_scripts.api.schemas.responses import (
    ArticleListResponse,
    ArticleResponse,
    ExecutionResponse,
)
from python_scripts.database.crud_articles import (
    count_competitor_articles,
    list_competitor_articles,
)
from python_scripts.database.crud_executions import (
    create_workflow_execution,
    get_workflow_execution,
    update_workflow_execution,
)
from python_scripts.utils.exceptions import WorkflowError
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/scraping", tags=["scraping"])


async def run_scraping_background(
    domains: List[str],
    max_articles_per_domain: int,
    execution_id: UUID,
) -> None:
    """
    Background task to run scraping workflow (T108 - US5).

    Args:
        domains: List of domains to scrape
        max_articles_per_domain: Maximum articles per domain
        execution_id: Execution ID
    """
    try:
        from python_scripts.database.db_session import AsyncSessionLocal

        # Create new session for background task
        async with AsyncSessionLocal() as db_session:
            # Get execution object
            execution = await get_workflow_execution(db_session, execution_id)
            if not execution:
                logger.error("Execution not found", execution_id=str(execution_id))
                return

            # Update execution status to running
            await update_workflow_execution(
                db_session,
                execution,
                status="running",
            )

            # Run scraping using orchestrator
            from python_scripts.agents.agent_orchestrator import EditorialAnalysisOrchestrator

            orchestrator = EditorialAnalysisOrchestrator(db_session)
            workflow_result = await orchestrator.run_scraping_workflow(
                domains=domains,
                max_articles_per_domain=max_articles_per_domain,
                execution_id=execution_id,
            )

            # Get execution again (in case it was updated by orchestrator)
            execution = await get_workflow_execution(db_session, execution_id)
            if execution:
                # Update execution with results
                await update_workflow_execution(
                    db_session,
                    execution,
                    status="completed",
                    output_data=workflow_result,
                )

            logger.info(
                "Scraping workflow completed",
                execution_id=str(execution_id),
                domains=domains,
                total_articles=workflow_result.get("total_articles_scraped", 0),
            )

    except WorkflowError as e:
        logger.error("Scraping workflow error", execution_id=str(execution_id), error=str(e))
        from python_scripts.database.db_session import AsyncSessionLocal
        async with AsyncSessionLocal() as db_session:
            execution = await get_workflow_execution(db_session, execution_id)
            if execution:
                await update_workflow_execution(
                    db_session,
                    execution,
                    status="failed",
                    error_message=str(e),
                )
    except Exception as e:
        logger.error("Unexpected error in scraping workflow", execution_id=str(execution_id), error=str(e))
        from python_scripts.database.db_session import AsyncSessionLocal
        async with AsyncSessionLocal() as db_session:
            execution = await get_workflow_execution(db_session, execution_id)
            if execution:
                await update_workflow_execution(
                    db_session,
                    execution,
                    status="failed",
                    error_message=f"Unexpected error: {str(e)}",
                )


@router.post(
    "/scrape",
    response_model=ExecutionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Scrape articles from domains",
    description="""
    Start scraping articles from specified domains and index them in Qdrant.
    
    This endpoint:
    1. Scrapes articles from the provided domains
    2. Saves them to PostgreSQL (competitor_articles table)
    3. Generates embeddings and indexes them in Qdrant vector database
    
    Supports two modes:
    - **Direct domains**: Provide 'domains' list directly (e.g., for client site)
    - **Auto-fetch competitors**: Provide 'client_domain' to fetch validated competitors
    """,
)
async def scrape_articles(
    request: ScrapingRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> ExecutionResponse:
    """
    Start scraping workflow for domains (T103 - US5).
    
    This is a simplified endpoint that scrapes articles and indexes them in Qdrant.
    Use this to index articles from your client site or any other domains.

    Args:
        request: Scraping request with either domains or client_domain
        background_tasks: FastAPI background tasks
        db: Database session

    Returns:
        Execution response with execution_id
    """
    try:
        domains_to_scrape = []
        
        # Mode 1: Explicit domains provided
        if request.domains:
            domains_to_scrape = request.domains
            logger.info("Using explicit domains", domains=domains_to_scrape)
        
        # Mode 2: Fetch validated competitors from client_domain
        elif request.client_domain:
            from sqlalchemy import select, desc
            from python_scripts.database.models import WorkflowExecution
            
            # Find latest completed competitor search for this domain
            stmt = (
                select(WorkflowExecution)
                .where(
                    WorkflowExecution.workflow_type == "competitor_search",
                    WorkflowExecution.status == "completed",
                    WorkflowExecution.input_data["domain"].astext == request.client_domain,
                )
                .order_by(desc(WorkflowExecution.start_time))
                .limit(1)
            )
            
            result = await db.execute(stmt)
            execution = result.scalar_one_or_none()
            
            if not execution or not execution.output_data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No competitor search results found for domain: {request.client_domain}. Please run competitor search first.",
                )
            
            # Extract validated competitors (only those with validated=True or manual=True)
            competitors_data = execution.output_data.get("competitors", [])
            if not competitors_data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No validated competitors found for domain: {request.client_domain}",
                )
            
            # Extract domains from validated competitors
            domains_to_scrape = [
                comp.get("domain")
                for comp in competitors_data
                if comp.get("domain") and not comp.get("excluded", False)
            ]
            
            if not domains_to_scrape:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No validated competitors found for domain: {request.client_domain}",
                )
            
            logger.info(
                "Fetched validated competitors",
                client_domain=request.client_domain,
                competitor_count=len(domains_to_scrape),
                domains=domains_to_scrape,
            )
        
        # Create workflow execution
        execution = await create_workflow_execution(
            db,
            workflow_type="scraping",
            input_data={
                "domains": domains_to_scrape,
                "max_articles_per_domain": request.max_articles_per_domain,
                "client_domain": request.client_domain if request.client_domain else None,
            },
            status="pending",
        )

        execution_id = execution.execution_id

        # Start background task
        background_tasks.add_task(
            run_scraping_background,
            domains=domains_to_scrape,
            max_articles_per_domain=request.max_articles_per_domain,
            execution_id=execution_id,
        )

        logger.info(
            "Scraping workflow started",
            execution_id=str(execution_id),
            domains=domains_to_scrape,
            mode="auto-fetch" if request.client_domain else "explicit",
        )

        return ExecutionResponse(
            execution_id=execution_id,
            status="pending",
            start_time=execution.start_time,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to start scraping workflow", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start scraping workflow: {e}",
        )


@router.post(
    "/competitors",
    response_model=ExecutionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Scrape competitor articles",
    description="Start scraping articles from competitor domains (T103 - US5).",
)
async def scrape_competitors(
    request: ScrapingRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> ExecutionResponse:
    """
    Start scraping workflow for competitor domains (T103 - US5).

    Supports two modes:
    1. Explicit domains: Provide 'domains' list directly
    2. Auto-fetch: Provide 'client_domain' to automatically fetch validated competitors

    Args:
        request: Scraping request with either domains or client_domain
        background_tasks: FastAPI background tasks
        db: Database session

    Returns:
        Execution response with execution_id
    """
    try:
        domains_to_scrape = []
        
        # Mode 1: Explicit domains provided
        if request.domains:
            domains_to_scrape = request.domains
            logger.info("Using explicit domains", domains=domains_to_scrape)
        
        # Mode 2: Fetch validated competitors from client_domain
        elif request.client_domain:
            from sqlalchemy import select, desc
            from python_scripts.database.models import WorkflowExecution
            
            # Find latest completed competitor search for this domain
            stmt = (
                select(WorkflowExecution)
                .where(
                    WorkflowExecution.workflow_type == "competitor_search",
                    WorkflowExecution.status == "completed",
                    WorkflowExecution.input_data["domain"].astext == request.client_domain,
                )
                .order_by(desc(WorkflowExecution.start_time))
                .limit(1)
            )
            
            result = await db.execute(stmt)
            execution = result.scalar_one_or_none()
            
            if not execution or not execution.output_data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No competitor search results found for domain: {request.client_domain}. Please run competitor search first.",
                )
            
            # Extract validated competitors (only those with validated=True or manual=True)
            competitors_data = execution.output_data.get("competitors", [])
            if not competitors_data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No validated competitors found for domain: {request.client_domain}",
                )
            
            # Extract domains from validated competitors
            # Competitors in the list are already validated (excluded ones are filtered out)
            domains_to_scrape = [
                comp.get("domain")
                for comp in competitors_data
                if comp.get("domain") and not comp.get("excluded", False)
            ]
            
            if not domains_to_scrape:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No validated competitors found for domain: {request.client_domain}",
                )
            
            logger.info(
                "Fetched validated competitors",
                client_domain=request.client_domain,
                competitor_count=len(domains_to_scrape),
                domains=domains_to_scrape,
            )
        
        # Create workflow execution
        execution = await create_workflow_execution(
            db,
            workflow_type="scraping",
            input_data={
                "domains": domains_to_scrape,
                "max_articles_per_domain": request.max_articles_per_domain,
                "client_domain": request.client_domain if request.client_domain else None,
            },
            status="pending",
        )

        execution_id = execution.execution_id

        # Start background task
        background_tasks.add_task(
            run_scraping_background,
            domains=domains_to_scrape,
            max_articles_per_domain=request.max_articles_per_domain,
            execution_id=execution_id,
        )

        logger.info(
            "Scraping workflow started",
            execution_id=str(execution_id),
            domains=domains_to_scrape,
            mode="auto-fetch" if request.client_domain else "explicit",
        )

        return ExecutionResponse(
            execution_id=execution_id,
            status="pending",
            start_time=execution.start_time,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to start scraping workflow", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start scraping workflow: {e}",
        )


@router.get(
    "/articles",
    response_model=ArticleListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get scraped articles",
    description="Retrieve scraped articles with optional filters (T104 - US5).",
)
async def get_articles(
    domain: Optional[str] = Query(None, description="Filter by domain"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of articles"),
    offset: int = Query(0, ge=0, description="Number of articles to skip"),
    db: AsyncSession = Depends(get_db),
) -> ArticleListResponse:
    """
    Get scraped articles with optional filters (T104 - US5).

    Args:
        domain: Optional domain filter
        limit: Maximum number of articles to return
        offset: Number of articles to skip
        db: Database session

    Returns:
        List of articles with pagination info
    """
    try:
        # Get articles from database
        articles = await list_competitor_articles(
            db,
            domain=domain,
            limit=limit,
            offset=offset,
        )

        # Get total count
        total = await count_competitor_articles(db, domain=domain)

        # Convert to response format
        article_responses = [
            ArticleResponse(
                id=article.id,
                domain=article.domain,
                url=article.url,
                title=article.title,
                author=article.author,
                published_date=article.published_date,
                word_count=article.word_count,
                created_at=article.created_at,
            )
            for article in articles
        ]

        logger.info(
            "Articles retrieved",
            domain=domain,
            count=len(article_responses),
            total=total,
        )

        return ArticleListResponse(
            articles=article_responses,
            total=total,
            limit=limit,
            offset=offset,
        )

    except Exception as e:
        logger.error("Failed to retrieve articles", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve articles: {e}",
        )

