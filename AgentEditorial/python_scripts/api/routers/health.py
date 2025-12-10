"""Health check endpoint."""

from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["Health"])


@router.get(
    "",
    summary="Health check",
    description="Check the health status of the API service. Returns service status and basic information.",
    responses={
        200: {
            "description": "Service is healthy",
            "content": {
                "application/json": {
                    "example": {
                        "status": "healthy",
                        "service": "agent-editorial",
                    }
                }
            }
        }
    },
)
async def health_check() -> dict:
    """
    Health check endpoint.
    
    Returns the health status of the API service. This endpoint can be used for:
    - Load balancer health checks
    - Monitoring and alerting
    - Service discovery
    
    Returns:
        Dictionary with status and service name
        
    Example:
        ```bash
        curl http://localhost:8000/api/v1/health
        ```
        
        Response:
        ```json
        {
            "status": "healthy",
            "service": "agent-editorial"
        }
        ```
    """
    return {
        "status": "healthy",
        "service": "agent-editorial",
    }

