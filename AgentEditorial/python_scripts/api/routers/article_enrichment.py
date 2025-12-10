"""API router for article enrichment."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.agents.trend_pipeline.article_enrichment.article_enricher import ArticleEnricher
from python_scripts.api.dependencies import get_db_session as get_db
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/articles", tags=["Article Enrichment"])


# ============================================================
# Request/Response Schemas
# ============================================================

class EnrichArticleRequest(BaseModel):
    """Request schema for enriching a single article."""
    
    article_id: int = Field(..., description="ArticleRecommendation ID", examples=[38])
    client_domain: str = Field(..., description="Client domain (e.g., 'innosys.fr')", examples=["innosys.fr"])
    
    class Config:
        json_schema_extra = {
            "example": {
                "article_id": 38,
                "client_domain": "innosys.fr"
            }
        }


class EnrichBatchRequest(BaseModel):
    """Request schema for enriching multiple articles."""
    
    article_ids: List[int] = Field(..., min_length=1, description="List of ArticleRecommendation IDs", examples=[[38, 39, 40]])
    client_domain: str = Field(..., description="Client domain (e.g., 'innosys.fr')", examples=["innosys.fr"])
    
    class Config:
        json_schema_extra = {
            "example": {
                "article_ids": [38, 39, 40],
                "client_domain": "innosys.fr"
            }
        }


class EnrichedArticleResponse(BaseModel):
    """Response schema for enriched article."""
    
    article_id: int
    original: dict
    enriched: dict
    client_context_used: Optional[dict] = None
    statistics_used: Optional[dict] = None
    error: Optional[str] = None


class EnrichedBatchResponse(BaseModel):
    """Response schema for batch enrichment."""
    
    results: List[EnrichedArticleResponse]
    total: int
    successful: int
    failed: int


# ============================================================
# Endpoints
# ============================================================

@router.post(
    "/enrich",
    response_model=EnrichedArticleResponse,
    summary="Enrich a single article recommendation",
    description="""
    Enrich a single article recommendation with client context and statistics.
    
    This endpoint:
    - Retrieves client context from site_analysis_results (editorial tone, keywords, audience, etc.)
    - Fetches topic statistics (competitor volume, velocity, priority score, coverage gap)
    - Uses LLM to enrich the outline with personalized sections and subsections
    - Personalizes the hook with client-specific language and statistics
    - Returns the enriched article structure ready for content creation
    """,
    responses={
        200: {
            "description": "Article enriched successfully",
            "content": {
                "application/json": {
                    "example": {
                        "article_id": 38,
                        "original": {
                            "title": "Article Title",
                            "hook": "Original hook",
                            "outline": ["Section 1", "Section 2"]
                        },
                        "enriched": {
                            "enriched_hook": "Personalized hook with client context",
                            "enriched_outline": {
                                "introduction": {
                                    "title": "Introduction Title",
                                    "subsections": [],
                                    "key_points": []
                                }
                            }
                        },
                        "client_context_used": {
                            "domain": "innosys.fr",
                            "editorial_tone": "Professional"
                        },
                        "statistics_used": {
                            "competitor_volume": 774,
                            "velocity": 0.5
                        }
                    }
                }
            }
        },
        404: {
            "description": "Article not found"
        }
    },
)
async def enrich_article(
    request: EnrichArticleRequest,
    db: AsyncSession = Depends(get_db),
) -> EnrichedArticleResponse:
    """
    Enrich a single article recommendation with client context and statistics.
    
    This endpoint enriches an article recommendation by:
    - Retrieving client context from site_analysis_results (editorial tone, keywords, audience, etc.)
    - Fetching topic statistics (competitor volume, velocity, priority score, coverage gap)
    - Using LLM to enrich the outline with personalized sections and subsections
    - Personalizing the hook with client-specific language and statistics
    - Returning the enriched article structure ready for content creation
    
    Args:
        request: Enrichment request with article_id and client_domain
        db: Database session
        
    Returns:
        Enriched article response with original and enriched versions
        
    Raises:
        HTTPException: 404 if article not found, 500 on enrichment failure
        
    Example:
        ```bash
        curl -X POST "http://localhost:8000/api/v1/articles/enrich" \\
          -H "Content-Type: application/json" \\
          -d '{"article_id": 38, "client_domain": "innosys.fr"}'
        ```
    """
    enricher = ArticleEnricher()
    
    try:
        result = await enricher.enrich_article(
            db_session=db,
            article_id=request.article_id,
            client_domain=request.client_domain,
        )
        
        return EnrichedArticleResponse(
            article_id=result["article_id"],
            original=result["original"],
            enriched=result["enriched"],
            client_context_used=result.get("client_context_used"),
            statistics_used=result.get("statistics_used"),
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error("Article enrichment failed", error=str(e), article_id=request.article_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Enrichment failed: {str(e)}",
        )


@router.post(
    "/enrich-batch",
    response_model=EnrichedBatchResponse,
    summary="Enrich multiple article recommendations",
)
async def enrich_articles_batch(
    request: EnrichBatchRequest,
    db: AsyncSession = Depends(get_db),
) -> EnrichedBatchResponse:
    """
    Enrich multiple article recommendations in batch.
    
    This endpoint processes multiple articles efficiently by:
    - Loading client context once (shared for all articles)
    - Enriching each article with its specific topic statistics
    - Returning results for all articles
    """
    enricher = ArticleEnricher()
    
    try:
        results = await enricher.enrich_articles_batch(
            db_session=db,
            article_ids=request.article_ids,
            client_domain=request.client_domain,
        )
        
        # Convert to response format
        enriched_results = []
        successful = 0
        failed = 0
        
        for result in results:
            if "error" in result:
                failed += 1
                enriched_results.append(
                    EnrichedArticleResponse(
                        article_id=result["article_id"],
                        original={},
                        enriched={},
                        error=result["error"],
                    )
                )
            else:
                successful += 1
                enriched_results.append(
                    EnrichedArticleResponse(
                        article_id=result["article_id"],
                        original=result["original"],
                        enriched=result["enriched"],
                        statistics_used=result.get("statistics_used"),
                    )
                )
        
        return EnrichedBatchResponse(
            results=enriched_results,
            total=len(results),
            successful=successful,
            failed=failed,
        )
        
    except Exception as e:
        logger.error("Batch enrichment failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch enrichment failed: {str(e)}",
        )


@router.get(
    "/{article_id}/enriched",
    response_model=EnrichedArticleResponse,
    summary="Get enriched version of an article (if available)",
)
async def get_enriched_article(
    article_id: int,
    client_domain: str,
    db: AsyncSession = Depends(get_db),
) -> EnrichedArticleResponse:
    """
    Get enriched version of an article recommendation.
    
    Note: This endpoint enriches the article on-the-fly. For cached results,
    consider storing enriched data in the database.
    """
    enricher = ArticleEnricher()
    
    try:
        result = await enricher.enrich_article(
            db_session=db,
            article_id=article_id,
            client_domain=client_domain,
        )
        
        return EnrichedArticleResponse(
            article_id=result["article_id"],
            original=result["original"],
            enriched=result["enriched"],
            client_context_used=result.get("client_context_used"),
            statistics_used=result.get("statistics_used"),
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error("Failed to get enriched article", error=str(e), article_id=article_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enrich article: {str(e)}",
        )



