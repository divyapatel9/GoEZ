"""
FastAPI Backend Server for Health Agent
Provides REST and SSE streaming endpoints.
"""

import uuid
from typing import Optional
from fastapi import FastAPI, APIRouter, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
import asyncio
import json

from .main import (
    stream_health_agent, 
    stream_health_agent_with_phases,
    continue_conversation_with_phases,
    run_health_agent, 
    get_session_history
)
from .memory import MongoDBMemory


# Create router - routes defined WITHOUT prefix (prefix added when included)
router = APIRouter(tags=["agent"])

# Standalone app for direct running
app = FastAPI(
    title="Health Agent API",
    description="API for querying Apple Health data using natural language",
    version="1.0.0",
)

# Add CORS middleware (only used when running standalone)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== Request/Response Models ====================

class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    message: str
    user_id: str = "default_user"
    session_id: Optional[str] = None
    collection_name: Optional[str] = None


class ChatResponse(BaseModel):
    """Response model for non-streaming chat."""
    session_id: str
    response: str
    phase: str
    has_report: bool


class SessionInfo(BaseModel):
    """Session information."""
    session_id: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    preview: Optional[str] = None


class HealthCheckResponse(BaseModel):
    """Health check response."""
    status: str
    version: str


# ==================== Endpoints ====================

@router.get("/")
@router.get("/health", response_model=HealthCheckResponse)
async def agent_health_check():
    """Health check endpoint."""
    return HealthCheckResponse(status="healthy", version="1.0.0")


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Non-streaming chat endpoint.
    
    Runs the health agent and returns the complete response.
    """
    session_id = request.session_id or str(uuid.uuid4())
    
    try:
        result = await run_health_agent(
            user_id=request.user_id,
            session_id=session_id,
            query=request.message,
            collection_name=request.collection_name,
        )
        
        # Extract final response from messages
        messages = result.get("messages", [])
        response_text = ""
        for msg in reversed(messages):
            if hasattr(msg, "content") and msg.content:
                response_text = msg.content
                break
        
        return ChatResponse(
            session_id=session_id,
            response=response_text,
            phase=result.get("current_phase", "complete"),
            has_report=result.get("final_report") is not None,
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    Streaming chat endpoint using Server-Sent Events.
    
    Streams tokens and phase transitions as they occur.
    Events:
        - session: Initial session info
        - phase: Phase transition (clarify, brief, research, report, complete)
        - token: Content token
        - tasks: Analysis tasks created
        - subagent: Sub-agent progress
        - done: Completion
        - error: Error occurred
        - interrupt: Waiting for user input (clarification)
    """
    session_id = request.session_id or str(uuid.uuid4())
    
    async def event_generator():
        try:
            # Send session ID first
            yield {
                "event": "session",
                "data": json.dumps({"session_id": session_id})
            }
            
            # Stream with phase tracking
            async for event in stream_health_agent_with_phases(
                user_id=request.user_id,
                session_id=session_id,
                query=request.message,
                collection_name=request.collection_name,
            ):
                yield event
            
            # Send completion event
            yield {
                "event": "done",
                "data": json.dumps({"status": "complete"})
            }
            
        except Exception as e:
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)})
            }
    
    return EventSourceResponse(event_generator())


@router.post("/chat/continue")
async def chat_continue(request: ChatRequest):
    """
    Continue a conversation from an interrupt (e.g., after clarification question).
    """
    if not request.session_id:
        raise HTTPException(status_code=400, detail="session_id is required to continue a conversation")
    
    async def event_generator():
        try:
            async for event in continue_conversation_with_phases(
                user_id=request.user_id,
                session_id=request.session_id,
                message=request.message,
            ):
                yield event
            
            yield {
                "event": "done",
                "data": json.dumps({"status": "complete"})
            }
            
        except Exception as e:
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)})
            }
    
    return EventSourceResponse(event_generator())


@router.get("/sessions/{user_id}")
async def get_user_sessions(
    user_id: str,
    limit: int = Query(default=10, ge=1, le=50)
):
    """
    Get recent sessions for a user.
    """
    try:
        memory = MongoDBMemory(user_id=user_id)
        sessions = await memory.get_recent_sessions(limit=limit)
        
        return {
            "user_id": user_id,
            "sessions": [
                SessionInfo(
                    session_id=s["session_id"],
                    created_at=s.get("created_at", "").isoformat() if s.get("created_at") else None,
                    updated_at=s.get("updated_at", "").isoformat() if s.get("updated_at") else None,
                    preview=s.get("preview", ""),
                ).dict()
                for s in sessions
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{user_id}/{session_id}/history")
async def get_session_history_endpoint(user_id: str, session_id: str):
    """
    Get conversation history for a specific session.
    """
    try:
        messages = get_session_history(user_id, session_id)
        
        return {
            "session_id": session_id,
            "messages": [
                {
                    "role": "user" if msg.type == "human" else "assistant",
                    "content": msg.content,
                }
                for msg in messages
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/sessions/{user_id}/{session_id}")
async def delete_session(user_id: str, session_id: str):
    """
    Delete a specific session.
    """
    try:
        memory = MongoDBMemory(user_id=user_id)
        await memory.clear_session(session_id)
        
        return {"status": "deleted", "session_id": session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Include router in standalone app (no prefix for standalone)
app.include_router(router)


# ==================== Server Runner ====================

def run_server(host: str = "0.0.0.0", port: int = 8000):
    """Run the FastAPI server."""
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
