"""
LangGraph state definitions for the Health Agent workflow.
"""

from typing import TypedDict, Annotated, List, Optional, Sequence
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from .schema import (
    AnalysisTask,
    SubAgentResult,
    ClarifiedIntent,
    AggregatedInsights,
    HealthReport,
)
from .config import settings


class HealthAgentState(TypedDict):
    """
    Main state for the Health Agent LangGraph workflow.
    
    This state is passed through all nodes and contains:
    - User/session identification
    - Message history (with reducer for persistence)
    - Phase-specific data structures
    """
    
    # User and Session Context
    user_id: str
    session_id: str
    collection_name: str  # MongoDB collection for this user's health data
    
    # Conversation History (uses add_messages reducer for proper merging)
    messages: Annotated[Sequence[BaseMessage], add_messages]
    
    # Phase 1: Clarification
    clarification_turns: int
    clarified_intent: Optional[ClarifiedIntent]
    
    # Phase 2: Research Brief
    analysis_tasks: List[AnalysisTask]
    
    # Phase 3: Supervisor/Research
    subagent_results: List[SubAgentResult]
    aggregated_insights: Optional[AggregatedInsights]
    
    # Phase 4: Report
    final_report: Optional[HealthReport]
    
    # Control Flow
    current_phase: str  # "clarify", "brief", "research", "report"
    needs_clarification: bool
    error: Optional[str]


def create_initial_state(
    user_id: str,
    session_id: str,
    collection_name: Optional[str] = None,
) -> HealthAgentState:
    """
    Create initial state for a new health agent session.
    
    Args:
        user_id: Unique identifier for the user
        session_id: Session/conversation identifier
        collection_name: MongoDB collection name (defaults to settings.health_data_collection)
    
    Returns:
        Initialized HealthAgentState
    """
    return HealthAgentState(
        user_id=user_id,
        session_id=session_id,
        collection_name=collection_name or settings.health_data_collection,
        messages=[],
        clarification_turns=0,
        clarified_intent=None,
        analysis_tasks=[],
        subagent_results=[],
        aggregated_insights=None,
        final_report=None,
        current_phase="clarify",
        needs_clarification=True,
        error=None,
    )


class SubAgentState(TypedDict):
    """
    State for individual sub-agent execution.
    Used by the factory-created analysis agents.
    """
    task: AnalysisTask
    collection_name: str
    messages: Annotated[Sequence[BaseMessage], add_messages]
    result: Optional[SubAgentResult]
    iterations: int
    max_iterations: int
