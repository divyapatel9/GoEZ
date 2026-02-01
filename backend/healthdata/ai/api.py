"""
AI Chat API Endpoints - FastAPI router for AI chat functionality.

Endpoints:
- POST /ai/chat - Send a message and get AI response
- GET /ai/chat/thread - Get chat thread for a chart
- GET /ai/charts - Get available charts for chat
- DELETE /ai/chat/thread - Clear chat thread
"""

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.healthdata.ai.graph import (
    get_orchestrator,
    get_memory_store,
    ChatMessage,
)
from backend.healthdata.ai.registry import get_charts_for_ui, get_chart_scope


router = APIRouter(prefix="/ai", tags=["ai-chat"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class ChatRequest(BaseModel):
    """Request body for chat endpoint."""
    user_id: str = Field(default="default_user", description="User identifier")
    chart_id: str = Field(..., description="Chart ID to scope the conversation")
    message: str = Field(..., description="User's message")
    start_date: date = Field(..., description="Start of date range for context")
    end_date: date = Field(..., description="End of date range for context")
    focus_date: Optional[date] = Field(None, description="Optional focus date")
    metric_key: Optional[str] = Field(None, description="Metric key for raw explorer")


class ChatResponseModel(BaseModel):
    """Response from chat endpoint."""
    answer: str
    evidence: list[str]
    confidence: str
    confidence_reason: str
    next_questions: list[str]
    context_summary: dict
    timestamp: str


class ThreadMessage(BaseModel):
    """A message in the chat thread."""
    role: str
    content: str
    timestamp: str
    metadata: Optional[dict] = None


class ThreadResponse(BaseModel):
    """Response containing chat thread."""
    user_id: str
    chart_id: str
    messages: list[ThreadMessage]
    count: int


class ChartInfo(BaseModel):
    """Information about an available chart."""
    chart_id: str
    display_name: str
    category: str
    quick_questions: list[str]


class ChartsResponse(BaseModel):
    """Response containing available charts."""
    charts: list[ChartInfo]
    count: int


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post("/chat", response_model=ChatResponseModel)
async def chat(request: ChatRequest) -> ChatResponseModel:
    """
    Send a message to the AI assistant and get a response.
    
    The AI will be scoped to the specified chart and will use the
    provided date range to build context from the user's health data.
    
    The response includes:
    - answer: The AI's response text
    - evidence: Specific facts from the data that support the answer
    - confidence: High/Medium/Low confidence level
    - next_questions: Suggested follow-up questions
    """
    # Validate chart_id
    scope = get_chart_scope(request.chart_id)
    if not scope:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown chart_id: {request.chart_id}"
        )
    
    # Validate date range
    if request.start_date > request.end_date:
        raise HTTPException(
            status_code=400,
            detail="start_date must be before end_date"
        )
    
    if (request.end_date - request.start_date).days > 365:
        raise HTTPException(
            status_code=400,
            detail="Date range cannot exceed 365 days"
        )
    
    # Get memory store and load history
    memory = get_memory_store()
    thread = memory.get_thread(request.user_id, request.chart_id)
    
    # Convert to ChatMessage objects
    chat_history = [
        ChatMessage(
            role=msg["role"],
            content=msg["content"],
            timestamp=datetime.fromisoformat(msg["timestamp"]),
        )
        for msg in thread
    ]
    
    # Process message
    orchestrator = get_orchestrator()
    
    try:
        response = orchestrator.process_message(
            user_id=request.user_id,
            chart_id=request.chart_id,
            user_message=request.message,
            start_date=request.start_date,
            end_date=request.end_date,
            focus_date=request.focus_date,
            metric_key=request.metric_key,
            chat_history=chat_history,
        )
    except ValueError as e:
        # Handle missing API key or config errors
        raise HTTPException(
            status_code=503,
            detail=f"AI service configuration error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing message: {str(e)}"
        )
    
    # Persist messages to memory
    timestamp = datetime.utcnow()
    
    memory.add_message(
        user_id=request.user_id,
        chart_id=request.chart_id,
        role="user",
        content=request.message,
        metadata={"date_range": f"{request.start_date} to {request.end_date}"},
    )
    
    memory.add_message(
        user_id=request.user_id,
        chart_id=request.chart_id,
        role="assistant",
        content=response.answer,
        metadata={
            "confidence": response.confidence,
            "evidence_count": len(response.evidence),
        },
    )
    
    return ChatResponseModel(
        answer=response.answer,
        evidence=response.evidence,
        confidence=response.confidence,
        confidence_reason=response.confidence_reason,
        next_questions=response.next_questions,
        context_summary=response.context_summary,
        timestamp=timestamp.isoformat(),
    )


@router.get("/chat/thread", response_model=ThreadResponse)
async def get_thread(
    user_id: str = Query(default="default_user", description="User identifier"),
    chart_id: str = Query(..., description="Chart ID"),
) -> ThreadResponse:
    """
    Get the chat thread for a user and chart.
    
    Returns all messages in the conversation history for the specified chart.
    """
    scope = get_chart_scope(chart_id)
    if not scope:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown chart_id: {chart_id}"
        )
    
    memory = get_memory_store()
    thread = memory.get_thread(user_id, chart_id)
    
    messages = [
        ThreadMessage(
            role=msg["role"],
            content=msg["content"],
            timestamp=msg["timestamp"],
            metadata=msg.get("metadata"),
        )
        for msg in thread
    ]
    
    return ThreadResponse(
        user_id=user_id,
        chart_id=chart_id,
        messages=messages,
        count=len(messages),
    )


@router.delete("/chat/thread")
async def clear_thread(
    user_id: str = Query(default="default_user", description="User identifier"),
    chart_id: str = Query(..., description="Chart ID"),
) -> dict:
    """
    Clear the chat thread for a user and chart.
    
    This removes all conversation history for the specified chart.
    """
    scope = get_chart_scope(chart_id)
    if not scope:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown chart_id: {chart_id}"
        )
    
    memory = get_memory_store()
    memory.clear_thread(user_id, chart_id)
    
    return {
        "status": "cleared",
        "user_id": user_id,
        "chart_id": chart_id,
    }


@router.get("/charts", response_model=ChartsResponse)
async def get_charts() -> ChartsResponse:
    """
    Get list of available charts for AI chat.
    
    Returns all charts that the AI can discuss, including their
    display names, categories, and suggested quick questions.
    """
    charts_data = get_charts_for_ui()
    
    charts = [
        ChartInfo(
            chart_id=c["chart_id"],
            display_name=c["display_name"],
            category=c["category"],
            quick_questions=c["quick_questions"],
        )
        for c in charts_data
    ]
    
    return ChartsResponse(
        charts=charts,
        count=len(charts),
    )


@router.get("/health")
async def ai_health_check() -> dict:
    """
    Health check for AI service.
    
    Verifies that the AI service is configured correctly.
    """
    import os
    
    has_api_key = bool(os.getenv("ANTHROPIC_API_KEY"))
    
    return {
        "status": "healthy" if has_api_key else "misconfigured",
        "api_key_configured": has_api_key,
        "charts_available": len(get_charts_for_ui()),
    }
