"""API router for execution tracking endpoints."""

import asyncio
import json
from typing import Dict, Set
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from sqlalchemy.ext.asyncio import AsyncSession

from python_scripts.api.dependencies import get_db_session as get_db
from python_scripts.api.schemas.responses import ExecutionResponse, ErrorResponse
from python_scripts.database.crud_executions import get_workflow_execution
from python_scripts.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/executions", tags=["executions"])

# WebSocket connection manager
class WebSocketManager:
    """Manages WebSocket connections for progress streaming."""
    
    def __init__(self) -> None:
        """Initialize the WebSocket manager."""
        self.active_connections: Dict[UUID, Set[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, execution_id: UUID) -> None:
        """Accept a WebSocket connection for an execution."""
        await websocket.accept()
        if execution_id not in self.active_connections:
            self.active_connections[execution_id] = set()
        self.active_connections[execution_id].add(websocket)
        logger.info("WebSocket connected", execution_id=str(execution_id))
    
    def disconnect(self, websocket: WebSocket, execution_id: UUID) -> None:
        """Remove a WebSocket connection."""
        if execution_id in self.active_connections:
            self.active_connections[execution_id].discard(websocket)
            if not self.active_connections[execution_id]:
                del self.active_connections[execution_id]
        logger.info("WebSocket disconnected", execution_id=str(execution_id))
    
    async def send_progress(self, execution_id: UUID, progress_data: Dict[str, any]) -> None:
        """Send progress update to all connected clients for an execution."""
        if execution_id in self.active_connections:
            disconnected = set()
            for websocket in self.active_connections[execution_id]:
                try:
                    await websocket.send_json(progress_data)
                except Exception as e:
                    logger.warning("Failed to send progress", execution_id=str(execution_id), error=str(e))
                    disconnected.add(websocket)
            
            # Remove disconnected websockets
            for ws in disconnected:
                self.disconnect(ws, execution_id)

# Global WebSocket manager instance
websocket_manager = WebSocketManager()


@router.get(
    "/{execution_id}",
    response_model=ExecutionResponse,
    summary="Get execution status",
    description="Get the status of a workflow execution by ID. Use this endpoint to poll for execution status.",
    responses={
        200: {
            "description": "Execution status retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "execution_id": "123e4567-e89b-12d3-a456-426614174000",
                        "status": "running",
                        "start_time": "2025-01-09T18:00:00Z",
                        "estimated_duration_minutes": 10,
                    }
                }
            }
        },
        404: {
            "description": "Execution not found",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Execution not found: 123e4567-e89b-12d3-a456-426614174000"
                    }
                }
            }
        }
    },
)
async def get_execution(
    execution_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ExecutionResponse:
    """
    Get workflow execution status.

    This endpoint allows you to poll for the status of a workflow execution.
    The execution status can be: `pending`, `running`, `completed`, or `failed`.
    
    For real-time progress updates, use the WebSocket endpoint: `/api/v1/executions/{execution_id}/stream`

    Args:
        execution_id: Execution UUID (from POST response)
        db: Database session

    Returns:
        Execution response with status, start time, and estimated duration
        
    Raises:
        HTTPException: 404 if execution not found
        
    Example:
        ```bash
        curl http://localhost:8000/api/v1/executions/123e4567-e89b-12d3-a456-426614174000
        ```
        
        Response:
        ```json
        {
            "execution_id": "123e4567-e89b-12d3-a456-426614174000",
            "status": "running",
            "start_time": "2025-01-09T18:00:00Z",
            "estimated_duration_minutes": 10
        }
        ```
    """
    execution = await get_workflow_execution(db, execution_id)
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution not found: {execution_id}",
        )

    # Calculate estimated duration if running
    estimated_duration = None
    if execution.status == "running" and execution.start_time:
        from datetime import datetime, timezone

        elapsed = datetime.now(timezone.utc) - execution.start_time
        # Rough estimate: 2 minutes per page
        if execution.input_data and "max_pages" in execution.input_data:
            max_pages = execution.input_data["max_pages"]
            estimated_duration = max_pages * 2  # minutes
        else:
            estimated_duration = int(elapsed.total_seconds() / 60) + 5  # Add buffer

    return ExecutionResponse(
        execution_id=execution.execution_id,
        status=execution.status,
        start_time=execution.start_time,
        estimated_duration_minutes=estimated_duration,
    )


@router.websocket("/{execution_id}/stream")
async def stream_execution_progress(
    websocket: WebSocket,
    execution_id: UUID,
) -> None:
    """
    WebSocket endpoint for real-time execution progress streaming.
    
    Connects to a WebSocket and receives real-time progress updates for a workflow execution.
    Progress updates are sent as JSON messages with the following structure:
    
    ```json
    {
        "step": "crawling",
        "progress": 25,
        "message": "Crawling pages...",
        "status": "running",
        "timestamp": "2025-01-09T18:00:00Z"
    }
    ```
    
    The connection will automatically close when the execution completes or fails.
    
    Args:
        websocket: WebSocket connection
        execution_id: Execution UUID to stream progress for
    
    Example:
        ```javascript
        const ws = new WebSocket('ws://localhost:8000/api/v1/executions/{execution_id}/stream');
        ws.onmessage = (event) => {
            const progress = JSON.parse(event.data);
            console.log(`Progress: ${progress.progress}% - ${progress.message}`);
        };
        ```
    """
    # Create database session for WebSocket
    from python_scripts.database.db_session import AsyncSessionLocal
    
    async with AsyncSessionLocal() as db:
        # Verify execution exists
        execution = await get_workflow_execution(db, execution_id)
        if not execution:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Execution not found")
            return
    
    # Connect to WebSocket manager
    await websocket_manager.connect(websocket, execution_id)
    
    try:
        # Send initial status
        await websocket.send_json({
            "step": "connected",
            "progress": 0,
            "message": f"Connected to execution {execution_id}",
            "status": execution.status,
            "execution_id": str(execution_id),
        })
        
        # Poll for updates until execution completes or fails
        last_status = execution.status
        while last_status in ("pending", "running"):
            await asyncio.sleep(1)  # Poll every second
            
            # Refresh execution status (create new session for each poll)
            async with AsyncSessionLocal() as poll_db:
                execution = await get_workflow_execution(poll_db, execution_id)
            if not execution:
                await websocket.send_json({
                    "step": "error",
                    "progress": 0,
                    "message": "Execution not found",
                    "status": "failed",
                })
                break
            
            # If status changed, send update
            if execution.status != last_status:
                last_status = execution.status
                await websocket.send_json({
                    "step": "status_change",
                    "progress": 100 if execution.status == "completed" else 0,
                    "message": f"Execution status: {execution.status}",
                    "status": execution.status,
                    "execution_id": str(execution_id),
                })
                
                # Close connection if execution is done
                if execution.status in ("completed", "failed"):
                    await websocket.send_json({
                        "step": "complete",
                        "progress": 100,
                        "message": f"Execution {execution.status}",
                        "status": execution.status,
                        "execution_id": str(execution_id),
                    })
                    break
            
            # Keep connection alive
            try:
                await websocket.receive_text()  # Non-blocking check for client disconnect
            except WebSocketDisconnect:
                break
            except Exception:
                pass  # Timeout or other non-critical error
        
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected", execution_id=str(execution_id))
    except Exception as e:
        logger.error("WebSocket error", execution_id=str(execution_id), error=str(e))
        try:
            await websocket.send_json({
                "step": "error",
                "progress": 0,
                "message": f"Error: {str(e)}",
                "status": "error",
            })
        except Exception:
            pass  # Connection may already be closed
    finally:
        websocket_manager.disconnect(websocket, execution_id)

