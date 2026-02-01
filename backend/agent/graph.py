"""
Main LangGraph Workflow Orchestration
Assembles the complete Health Agent graph with all nodes and edges.
"""

from typing import Literal
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt

from .state import HealthAgentState
from .nodes import (
    clarify_node,
    should_continue_clarifying,
    brief_node,
    supervisor_node,
    report_node,
)
from .memory import get_mongodb_checkpointer


def wait_for_user_node(state: HealthAgentState) -> dict:
    """
    Node that interrupts execution to wait for user input.
    Uses LangGraph's interrupt mechanism to pause the graph.
    """
    # Interrupt the graph - this will pause execution and return control
    # The graph will resume when the user provides new input
    user_input = interrupt("Waiting for user clarification response...")
    
    # When resumed, the user_input contains the new message
    from langchain_core.messages import HumanMessage
    return {
        "messages": [HumanMessage(content=user_input)],
    }


def create_health_agent_graph(use_mongodb_checkpointer: bool = True):
    """
    Create the main Health Agent LangGraph workflow.
    
    Graph Structure:
        START → clarify → [conditional] → brief → supervisor → report → END
                   ↑__________|
                   (loop if needs clarification)
    
    Args:
        use_mongodb_checkpointer: Whether to use MongoDB for state persistence
        
    Returns:
        Compiled LangGraph workflow
    """
    # Create the state graph
    workflow = StateGraph(HealthAgentState)
    
    # Add nodes
    workflow.add_node("clarify", clarify_node)
    workflow.add_node("wait_for_user", wait_for_user_node)
    workflow.add_node("brief", brief_node)
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("report", report_node)
    
    # Add edges
    # Start with clarification
    workflow.add_edge(START, "clarify")
    
    # Conditional edge from clarify
    workflow.add_conditional_edges(
        "clarify",
        route_after_clarify,
        {
            "wait_for_user": "wait_for_user",  # Pause for user input
            "brief": "brief",                   # Proceed to brief generation
        }
    )
    
    # After user responds, go back to clarify
    workflow.add_edge("wait_for_user", "clarify")
    
    # Linear flow after clarification
    workflow.add_edge("brief", "supervisor")
    workflow.add_edge("supervisor", "report")
    workflow.add_edge("report", END)
    
    # Get checkpointer
    if use_mongodb_checkpointer:
        try:
            checkpointer = get_mongodb_checkpointer()
        except Exception:
            checkpointer = MemorySaver()
    else:
        checkpointer = MemorySaver()
    
    # Compile the graph
    compiled = workflow.compile(checkpointer=checkpointer)
    
    return compiled


def route_after_clarify(state: HealthAgentState) -> Literal["wait_for_user", "brief"]:
    """
    Determine whether to wait for user input or proceed to brief.
    
    Args:
        state: Current workflow state
        
    Returns:
        Next node name
    """
    result = should_continue_clarifying(state)
    if result == "clarify":
        return "wait_for_user"  # Pause for user input
    return "brief"


def create_simple_graph():
    """
    Create a simplified graph without clarification loop.
    Useful for testing or when intent is already clear.
    
    Returns:
        Compiled LangGraph workflow
    """
    workflow = StateGraph(HealthAgentState)
    
    # Add nodes
    workflow.add_node("brief", brief_node)
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("report", report_node)
    
    # Linear flow
    workflow.add_edge(START, "brief")
    workflow.add_edge("brief", "supervisor")
    workflow.add_edge("supervisor", "report")
    workflow.add_edge("report", END)
    
    # Compile with memory saver
    compiled = workflow.compile(checkpointer=MemorySaver())
    
    return compiled


# Pre-compiled graph instance for reuse
_graph_instance = None


def get_health_agent_graph():
    """
    Get or create the singleton Health Agent graph instance.
    
    Returns:
        Compiled LangGraph workflow
    """
    global _graph_instance
    if _graph_instance is None:
        _graph_instance = create_health_agent_graph()
    return _graph_instance
