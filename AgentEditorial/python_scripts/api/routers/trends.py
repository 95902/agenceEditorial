"""Trends analysis API router (T128, T129, T133 - US7)."""

from typing import List
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.agents.agent_topic_modeling import TopicModelingAgent
from python_scripts.api.dependencies import get_db_session as get_db
from python_scripts.api.schemas.requests import TrendsAnalysisRequest
from python_scripts.api.schemas.responses import (
    ExecutionResponse,
    TrendsAnalysisResponse,
    TrendsTopicsResponse,
    TopicInfoResponse,
    TopicKeywordResponse,
)
from python_scripts.database.crud_executions import (
    create_workflow_execution,
    get_workflow_execution,
    update_workflow_execution,
)
from python_scripts.database.crud_topics import (
    get_bertopic_analysis_by_id,
    get_latest_bertopic_analysis,
    list_bertopic_analyses,
)
from python_scripts.utils.exceptions import WorkflowError
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/trends", tags=["trends"])

# Initialize agent
topic_modeling_agent = TopicModelingAgent()


async def run_trends_analysis_background(
    execution_id: UUID,
    input_data: dict,
    db: AsyncSession,
) -> None:
    """
    Background task runner for trends analysis (T133 - US7).
    
    Args:
        execution_id: Execution ID
        input_data: Input data for analysis
        db: Database session
    """
    try:
        # Update status to running
        execution = await get_workflow_execution(db, execution_id)
        if execution:
            await update_workflow_execution(
                db,
                execution,
                status="running",
            )
        
        # Run topic modeling agent
        result = await topic_modeling_agent.execute(
            execution_id,
            input_data,
            db_session=db,
        )
        
        # Update execution with results
        if execution:
            await update_workflow_execution(
                db,
                execution,
                status="completed",
                output_data=result,
                was_success=True,
            )
        
        logger.info(
            "Trends analysis completed",
            execution_id=str(execution_id),
            num_topics=result.get("statistics", {}).get("num_topics", 0),
        )
        
    except Exception as e:
        logger.error(
            "Trends analysis failed",
            execution_id=str(execution_id),
            error=str(e),
        )
        
        # Update execution with error
        execution = await get_workflow_execution(db, execution_id)
        if execution:
            await update_workflow_execution(
                db,
                execution,
                status="failed",
                error_message=str(e),
                was_success=False,
            )


@router.post(
    "/analyze",
    response_model=ExecutionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start trends analysis",
    description="Start a BERTopic analysis workflow. Provide either 'client_domain' (auto-fetch competitors) or 'domains' (explicit list) (T128 - US7)",
)
async def analyze_trends(
    request: TrendsAnalysisRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> ExecutionResponse:
    """
    Start trends analysis workflow (T128 - US7).
    
    Supports two modes:
    1. client_domain: Automatically fetch validated competitors for the client domain
    2. domains: Explicit list of domains to analyze
    
    Args:
        request: Trends analysis request
        background_tasks: FastAPI background tasks
        db: Database session
        
    Returns:
        Execution response with execution_id
    """
    try:
        domains_to_analyze = []
        
        # Mode 1: Explicit domains provided
        if request.domains:
            domains_to_analyze = request.domains
            logger.info("Using explicit domains", domains=domains_to_analyze)
        
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
            for comp in competitors_data:
                validation_status = comp.get("validation_status", "validated")
                validated = comp.get("validated", False)
                excluded = comp.get("excluded", False)
                
                # Include only validated or manual competitors (not excluded)
                if not excluded and (validation_status in ["validated", "manual"] or validated):
                    domain = comp.get("domain")
                    if domain:
                        domains_to_analyze.append(domain)
            
            if not domains_to_analyze:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No validated competitors found for domain: {request.client_domain}. Please validate competitors first.",
                )
            
            logger.info(
                "Using validated competitors from client domain",
                client_domain=request.client_domain,
                competitor_count=len(domains_to_analyze),
                domains=domains_to_analyze,
            )
        
        # Prepare input data
        input_data = {
            "domains": domains_to_analyze,
            "time_window_days": request.time_window_days,
            "client_domain": request.client_domain if request.client_domain else None,
        }
        
        if request.min_topic_size is not None:
            input_data["min_topic_size"] = request.min_topic_size
        
        if request.nr_topics is not None:
            input_data["nr_topics"] = request.nr_topics
        
        # Pass Qdrant and filtering parameters
        input_data["use_qdrant_embeddings"] = request.use_qdrant_embeddings
        input_data["filter_semantic_duplicates"] = request.filter_semantic_duplicates
        
        if request.min_semantic_quality is not None:
            input_data["min_semantic_quality"] = request.min_semantic_quality
        
        # Create workflow execution
        execution = await create_workflow_execution(
            db,
            workflow_type="trends_analysis",
            input_data=input_data,
            status="pending",
        )
        
        # Add background task
        background_tasks.add_task(
            run_trends_analysis_background,
            execution.execution_id,
            input_data,
            db,
        )
        
        logger.info(
            "Trends analysis started",
            execution_id=str(execution.execution_id),
            client_domain=request.client_domain,
            domains=domains_to_analyze,
        )
        
        return ExecutionResponse(
            execution_id=execution.execution_id,
            status="pending",
            start_time=execution.start_time,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to start trends analysis", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start trends analysis: {str(e)}",
        ) from e


@router.get(
    "/topics",
    response_model=TrendsTopicsResponse,
    summary="Get trends topics",
    description="Get topics from the latest or specified trends analysis. Supports filtering by client_domain, domain, analysis_id, or time_window_days (T129 - US7)",
)
async def get_trends_topics(
    client_domain: str | None = None,
    time_window_days: int | None = None,
    domain: str | None = None,
    analysis_id: int | None = None,
    db: AsyncSession = Depends(get_db),
) -> TrendsTopicsResponse:
    """
    Get trends topics (T129 - US7).
    
    Args:
        client_domain: Client domain to get topics for (finds latest analysis for this client's competitors)
        time_window_days: Filter by time window (optional)
        domain: Filter by competitor domain (optional)
        analysis_id: Specific analysis ID (optional, if not provided returns latest)
        db: Database session
        
    Returns:
        Trends topics response
    """
    try:
        # Get analysis
        if analysis_id:
            analysis = await get_bertopic_analysis_by_id(db, analysis_id)
            if not analysis:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Analysis {analysis_id} not found",
                )
        elif client_domain:
            # Find latest workflow execution for this client_domain
            from sqlalchemy import select, desc
            from python_scripts.database.models import WorkflowExecution
            
            stmt = (
                select(WorkflowExecution)
                .where(
                    WorkflowExecution.workflow_type == "trends_analysis",
                    WorkflowExecution.status == "completed",
                    WorkflowExecution.input_data["client_domain"].astext == client_domain,
                )
                .order_by(desc(WorkflowExecution.start_time))
                .limit(1)
            )
            
            result = await db.execute(stmt)
            execution = result.scalar_one_or_none()
            
            if not execution or not execution.input_data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No trends analysis found for client domain: {client_domain}. Please run trends analysis first.",
                )
            
            # Get domains and time_window from execution
            execution_domains = set(execution.input_data.get("domains", []))
            execution_time_window = execution.input_data.get("time_window_days")
            
            # Find analysis matching these domains and time window
            # Get all analyses and find the best match
            all_analyses = await list_bertopic_analyses(
                db,
                time_window_days=execution_time_window if time_window_days is None else time_window_days,
                limit=100,
            )
            
            # Find analysis with matching domains (exact match preferred)
            analysis = None
            best_match = None
            best_match_score = 0
            
            for candidate in all_analyses:
                if isinstance(candidate.domains_included, dict):
                    candidate_domains = set(candidate.domains_included.keys())
                    # Exact match
                    if candidate_domains == execution_domains:
                        analysis = candidate
                        break
                    # Partial match (at least 80% of domains match)
                    elif execution_domains:
                        match_ratio = len(candidate_domains & execution_domains) / len(execution_domains)
                        if match_ratio >= 0.8 and match_ratio > best_match_score:
                            best_match = candidate
                            best_match_score = match_ratio
            
            # Use best match if no exact match found
            if not analysis and best_match:
                analysis = best_match
            
            # If still no match, use the latest analysis created after the execution
            if not analysis and execution.start_time:
                # Get analyses ordered by creation date
                recent_analyses = await list_bertopic_analyses(
                    db,
                    limit=10,
                )
                # Find the first analysis created after execution start
                for candidate in recent_analyses:
                    if candidate.created_at and candidate.created_at >= execution.start_time:
                        analysis = candidate
                        break
            
            if not analysis:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No trends analysis found for client domain: {client_domain}. The analysis may not have been stored yet.",
                )
        else:
            analysis = await get_latest_bertopic_analysis(db, domain=domain)
            if not analysis:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No trends analysis found",
                )
        
        # Convert topics to response format
        topics_list = []
        for topic_id, topic_data in analysis.topics.items():
            # Extract keywords (list of tuples (word, score) or just words)
            keywords = topic_data.get("keywords", [])
            keywords_formatted = []
            
            if keywords:
                try:
                    # Try to determine the format
                    first_kw = keywords[0] if keywords else None
                    
                    if first_kw is None:
                        pass  # Empty keywords
                    elif isinstance(first_kw, (list, tuple)) and len(first_kw) >= 2:
                        # Format: [(word, score), ...] or [[word, score], ...] (JSON serialized tuples)
                        keywords_formatted = [
                            TopicKeywordResponse(
                                word=str(kw[0]),
                                score=float(kw[1]) if len(kw) > 1 else 1.0
                            )
                            for kw in keywords[:10] if isinstance(kw, (list, tuple)) and len(kw) >= 1
                        ]
                    elif isinstance(first_kw, dict):
                        # Format: [{"word": "de", "score": 0.5}, ...] or [{"de": 0.5}, ...]
                        for kw in keywords[:10]:
                            if not isinstance(kw, dict):
                                continue
                            if "word" in kw and "score" in kw:
                                keywords_formatted.append(
                                    TopicKeywordResponse(
                                        word=str(kw["word"]),
                                        score=float(kw["score"])
                                    )
                                )
                            elif len(kw) == 1:
                                # Format: {"de": 0.5}
                                word, score = next(iter(kw.items()))
                                keywords_formatted.append(
                                    TopicKeywordResponse(
                                        word=str(word),
                                        score=float(score) if isinstance(score, (int, float)) else 1.0
                                    )
                                )
                    else:
                        # Format: [word, ...] (strings only)
                        keywords_formatted = [
                            TopicKeywordResponse(word=str(kw), score=1.0)
                            for kw in keywords[:10] if isinstance(kw, str)
                        ]
                except Exception as e:
                    logger.warning(
                        "Failed to parse keywords for topic",
                        topic_id=topic_id,
                        error=str(e),
                        keywords_preview=str(keywords[:3]) if keywords else "empty"
                    )
                    # Fallback: try to extract any strings as keywords
                    keywords_formatted = [
                        TopicKeywordResponse(word=str(kw), score=1.0)
                        for kw in keywords[:10]
                        if isinstance(kw, str) or (isinstance(kw, (list, tuple)) and len(kw) > 0)
                    ]
            
            # Ensure count is an integer (handle None case)
            count_value = topic_data.get("count")
            if count_value is None:
                count_value = 0
            else:
                try:
                    count_value = int(count_value)
                except (ValueError, TypeError):
                    count_value = 0
            
            topics_list.append(
                TopicInfoResponse(
                    topic_id=int(topic_id),
                    name=topic_data.get("name", f"Topic {topic_id}"),
                    keywords=keywords_formatted,
                    count=count_value,
                )
            )
        
        # Extract emerging topics if available
        emerging_topics_list = []
        if hasattr(analysis, "topics_over_time") and analysis.topics_over_time:
            # Try to identify emerging topics from evolution data
            # This is a simplified version - full implementation would compare with previous analysis
            pass
        
        # Count total articles (would need to query articles table)
        total_articles = sum(topic.count for topic in topics_list)
        
        return TrendsTopicsResponse(
            analysis_id=analysis.id,
            analysis_date=analysis.analysis_date.isoformat(),
            time_window_days=analysis.time_window_days,
            domains_included=list(analysis.domains_included.keys()) if isinstance(analysis.domains_included, dict) else [],
            topics=topics_list,
            emerging_topics=emerging_topics_list,
            total_topics=len(topics_list),
            total_articles=total_articles,
            visualizations=analysis.visualizations,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get trends topics", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get trends topics: {str(e)}",
        ) from e

