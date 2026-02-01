"""
LangGraph Orchestrator - AI chat workflow graph.

This module implements the chat orchestration using a simple graph pattern:
1. Load context and memory
2. Build prompt with chart-specific guardrails
3. Generate response via LLM
4. Validate and filter response
5. Persist to memory

Note: Using a simple orchestrator pattern instead of full LangGraph
to minimize dependencies while maintaining the same flow.
"""

import json
import os
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Optional

from anthropic import Anthropic

from backend.healthdata.ai.context_builder import build_chart_context, ChartContext
from backend.healthdata.ai.prompts import (
    build_system_prompt,
    build_context_prompt,
    check_high_risk_query,
    build_high_risk_response,
)
from backend.healthdata.ai.validator import (
    validate_response,
    parse_llm_response,
)
from backend.healthdata.ai.registry import get_chart_scope


@dataclass
class ChatMessage:
    """A single chat message."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    context_ref: Optional[str] = None  # Reference to context used


@dataclass
class ChatState:
    """State for a chat conversation."""
    user_id: str
    chart_id: str
    messages: list[ChatMessage] = field(default_factory=list)
    context: Optional[ChartContext] = None
    last_response: Optional[dict] = None


@dataclass
class ChatResponse:
    """Response from the chat orchestrator."""
    answer: str
    evidence: list[str]
    confidence: str
    confidence_reason: str
    next_questions: list[str]
    context_summary: dict
    validation_warnings: list[str] = field(default_factory=list)


def _get_anthropic_client() -> Anthropic:
    """Get Anthropic client with API key from environment."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")
    return Anthropic(api_key=api_key)


def _format_messages_for_api(
    messages: list[ChatMessage],
    max_messages: int = 10
) -> list[dict]:
    """Format chat messages for Anthropic API."""
    # Take only the last N messages to stay within context limits
    recent = messages[-max_messages:] if len(messages) > max_messages else messages
    
    return [
        {"role": msg.role, "content": msg.content}
        for msg in recent
    ]


def _call_llm(
    system_prompt: str,
    messages: list[dict],
    temperature: float = 0.3
) -> str:
    """Call the LLM and get response."""
    client = _get_anthropic_client()
    
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1500,
        temperature=temperature,
        system=system_prompt,
        messages=messages,
    )
    
    return response.content[0].text


# =============================================================================
# ORCHESTRATOR
# =============================================================================

class ChatOrchestrator:
    """
    Orchestrates AI chat for health analytics dashboard.
    
    Flow:
    1. Build chart context (deterministic, no LLM)
    2. Check for high-risk queries
    3. Build system prompt with guardrails
    4. Call LLM with context
    5. Validate response
    6. Return structured response
    """
    
    def __init__(self):
        self._client: Optional[Anthropic] = None
    
    @property
    def client(self) -> Anthropic:
        if self._client is None:
            self._client = _get_anthropic_client()
        return self._client
    
    def process_message(
        self,
        user_id: str,
        chart_id: str,
        user_message: str,
        start_date: date,
        end_date: date,
        focus_date: Optional[date] = None,
        metric_key: Optional[str] = None,
        chat_history: Optional[list[ChatMessage]] = None,
    ) -> ChatResponse:
        """
        Process a user message and generate a response.
        
        This is the main entry point for chat interactions.
        """
        chat_history = chat_history or []
        
        # Step 1: Build chart context (deterministic)
        context = build_chart_context(
            chart_id=chart_id,
            start_date=start_date,
            end_date=end_date,
            focus_date=focus_date,
            metric_key=metric_key,
        )
        context_dict = context.to_dict()
        
        # Step 2: Check for high-risk queries
        is_high_risk, risk_area, specific_concern = check_high_risk_query(user_message)
        
        if is_high_risk:
            # Return cautious response without full LLM call
            high_risk_response = build_high_risk_response(
                risk_area=risk_area,
                specific_concern=specific_concern,
                context_dict=context_dict,
            )
            
            return ChatResponse(
                answer=high_risk_response["answer"],
                evidence=high_risk_response["evidence"],
                confidence=high_risk_response["confidence"],
                confidence_reason=high_risk_response["confidence_reason"],
                next_questions=high_risk_response["next_questions"],
                context_summary=self._build_context_summary(context_dict),
                validation_warnings=["High-risk query detected; provided cautious guidance"],
            )
        
        # Step 3: Build system prompt
        system_prompt = build_system_prompt(chart_id)
        context_prompt = build_context_prompt(context_dict)
        full_system_prompt = system_prompt + "\n\n" + context_prompt
        
        # Step 4: Prepare messages for LLM
        api_messages = _format_messages_for_api(chat_history)
        api_messages.append({"role": "user", "content": user_message})
        
        # Step 5: Call LLM
        try:
            raw_response = _call_llm(
                system_prompt=full_system_prompt,
                messages=api_messages,
                temperature=0.3,
            )
        except Exception as e:
            # Fallback response on LLM error
            return ChatResponse(
                answer=f"I'm having trouble processing your request right now. Please try again in a moment.",
                evidence=[],
                confidence="Low",
                confidence_reason="LLM service error",
                next_questions=self._get_default_questions(chart_id),
                context_summary=self._build_context_summary(context_dict),
                validation_warnings=[f"LLM error: {str(e)}"],
            )
        
        # Step 6: Parse and validate response
        parsed_response = parse_llm_response(raw_response)
        validation_result = validate_response(
            response=parsed_response,
            context=context_dict,
            strict_mode=True,
        )
        
        validated = validation_result.response
        
        return ChatResponse(
            answer=validated.get("answer", ""),
            evidence=validated.get("evidence", []),
            confidence=validated.get("confidence", "Medium"),
            confidence_reason=validated.get("confidence_reason", ""),
            next_questions=validated.get("next_questions", []),
            context_summary=self._build_context_summary(context_dict),
            validation_warnings=validation_result.warnings,
        )
    
    def _build_context_summary(self, context_dict: dict) -> dict:
        """Build a summary of the context for response metadata."""
        return {
            "chart_id": context_dict.get("chart_id"),
            "date_range": context_dict.get("date_range"),
            "focus_date": context_dict.get("focus_date"),
            "data_quality": {
                "coverage_percent": context_dict.get("data_quality", {}).get("coverage_percent", 0),
                "days_with_data": context_dict.get("data_quality", {}).get("days_with_data", 0),
            },
            "confidence_level": context_dict.get("confidence_level"),
        }
    
    def _get_default_questions(self, chart_id: str) -> list[str]:
        """Get default questions for a chart."""
        scope = get_chart_scope(chart_id)
        if scope:
            return scope.quick_questions
        return [
            "What patterns do you see?",
            "How does this compare to my baseline?",
            "What should I focus on?",
        ]


# =============================================================================
# SIMPLE MEMORY STORE (in-memory for now, can be upgraded to MongoDB)
# =============================================================================

class MemoryStore:
    """
    Simple in-memory store for chat threads.
    
    In production, this would be backed by MongoDB.
    For now, using in-memory dict with persistence hooks.
    """
    
    def __init__(self):
        self._threads: dict[str, list[dict]] = {}  # key: user_id:chart_id
        self._summaries: dict[str, dict] = {}
    
    def _make_key(self, user_id: str, chart_id: str) -> str:
        return f"{user_id}:{chart_id}"
    
    def get_thread(self, user_id: str, chart_id: str) -> list[dict]:
        """Get chat thread for user and chart."""
        key = self._make_key(user_id, chart_id)
        return self._threads.get(key, [])
    
    def add_message(
        self,
        user_id: str,
        chart_id: str,
        role: str,
        content: str,
        metadata: Optional[dict] = None
    ) -> None:
        """Add a message to the thread."""
        key = self._make_key(user_id, chart_id)
        if key not in self._threads:
            self._threads[key] = []
        
        self._threads[key].append({
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
        })
        
        # Keep only last 50 messages per thread
        if len(self._threads[key]) > 50:
            self._threads[key] = self._threads[key][-50:]
    
    def clear_thread(self, user_id: str, chart_id: str) -> None:
        """Clear chat thread."""
        key = self._make_key(user_id, chart_id)
        self._threads.pop(key, None)
    
    def get_summary(self, user_id: str, chart_id: str) -> Optional[dict]:
        """Get conversation summary."""
        key = self._make_key(user_id, chart_id)
        return self._summaries.get(key)
    
    def update_summary(self, user_id: str, chart_id: str, summary: dict) -> None:
        """Update conversation summary."""
        key = self._make_key(user_id, chart_id)
        self._summaries[key] = {
            **summary,
            "updated_at": datetime.utcnow().isoformat(),
        }


# Global instances
_orchestrator: Optional[ChatOrchestrator] = None
_memory_store: Optional[MemoryStore] = None


def get_orchestrator() -> ChatOrchestrator:
    """Get or create the chat orchestrator."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = ChatOrchestrator()
    return _orchestrator


def get_memory_store() -> MemoryStore:
    """Get or create the memory store."""
    global _memory_store
    if _memory_store is None:
        _memory_store = MemoryStore()
    return _memory_store
