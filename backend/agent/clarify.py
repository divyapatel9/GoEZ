"""
Phase 1: Clarify Node
Handles initial user interaction to clarify their health query intent.
"""

from typing import Dict, Any, Literal
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from ..config import get_llm, settings
from ..state import HealthAgentState
from ..schema import ClarifiedIntent, TimeRange, TimeRangeType
from ..prompts import CLARIFY_SYSTEM_PROMPT
import json


async def clarify_node(state: HealthAgentState) -> Dict[str, Any]:
    """
    Clarify the user's health query.
    
    This node:
    1. Analyzes the user's question
    2. Asks clarifying questions if needed
    3. Produces a structured ClarifiedIntent when ready
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state with clarification results
    """
    llm = get_llm(temperature=0.7)
    messages = list(state["messages"])
    clarification_turns = state.get("clarification_turns", 0)
    
    # Build the prompt - Anthropic requires single system message
    full_system_prompt = CLARIFY_SYSTEM_PROMPT + """

Based on the conversation, determine if you have enough information to proceed with analysis.

If you have enough clarity, respond with a JSON block containing the structured intent:
```json
{
    "clarification_complete": true,
    "original_query": "user's original question",
    "health_domains": ["sleep", "activity", etc.],
    "specific_metrics": ["steps", "sleep_hours", etc.],
    "time_context": {"range_type": "relative", "last_n_days": 30},
    "comparison_requested": false,
    "goal_context": null
}
```

If you need more information, respond conversationally with your clarifying questions.
Do NOT include the JSON block if you're asking questions.
"""
    
    prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content=full_system_prompt),
        MessagesPlaceholder(variable_name="messages"),
    ])
    
    # Invoke the LLM
    chain = prompt | llm
    response = await chain.ainvoke({"messages": messages})
    
    # Parse the response
    response_text = response.content
    clarified_intent = None
    needs_clarification = True
    
    # Check if response contains structured intent
    if "```json" in response_text and '"clarification_complete": true' in response_text:
        try:
            # Extract JSON from response
            json_start = response_text.find("```json") + 7
            json_end = response_text.find("```", json_start)
            json_str = response_text[json_start:json_end].strip()
            
            intent_data = json.loads(json_str)
            
            # Build ClarifiedIntent
            time_context = intent_data.get("time_context", {})
            clarified_intent = ClarifiedIntent(
                original_query=intent_data.get("original_query", ""),
                health_domains=intent_data.get("health_domains", []),
                specific_metrics=intent_data.get("specific_metrics", []),
                time_context=TimeRange(
                    range_type=TimeRangeType(time_context.get("range_type", "relative")),
                    last_n_days=time_context.get("last_n_days", 30),
                ),
                comparison_requested=intent_data.get("comparison_requested", False),
                comparison_details=intent_data.get("comparison_details"),
                goal_context=intent_data.get("goal_context"),
                clarification_complete=True,
                clarification_questions=[],
            )
            needs_clarification = False
            
            # Create a cleaner response message
            clean_response = f"I understand! You want to analyze your {', '.join(clarified_intent.health_domains)} data"
            if clarified_intent.specific_metrics:
                clean_response += f", focusing on {', '.join(clarified_intent.specific_metrics)}"
            clean_response += f" over the last {clarified_intent.time_context.last_n_days} days."
            clean_response += " Let me analyze this for you..."
            
            response_message = AIMessage(content=clean_response)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            # If parsing fails, treat as clarifying response
            response_message = AIMessage(content=response_text)
    else:
        # Regular clarifying response
        response_message = AIMessage(content=response_text)
    
    return {
        "messages": [response_message],
        "clarification_turns": clarification_turns + 1,
        "clarified_intent": clarified_intent,
        "needs_clarification": needs_clarification,
        "current_phase": "clarify" if needs_clarification else "brief",
    }


def should_continue_clarifying(state: HealthAgentState) -> Literal["clarify", "brief"]:
    """
    Determine if we should continue clarifying or proceed to brief generation.
    
    Args:
        state: Current workflow state
        
    Returns:
        Next node to route to
    """
    # Check if clarification is complete
    if not state.get("needs_clarification", True):
        return "brief"
    
    # Check if we've exceeded max clarification turns
    if state.get("clarification_turns", 0) >= settings.max_clarification_turns:
        return "brief"
    
    # Check if we have a clarified intent
    if state.get("clarified_intent") is not None:
        return "brief"
    
    return "clarify"


def extract_intent_from_simple_query(query: str) -> ClarifiedIntent:
    """
    Extract intent from a simple, clear query without LLM.
    Used as a fallback or for very straightforward queries.
    
    Args:
        query: User's query string
        
    Returns:
        Basic ClarifiedIntent
    """
    query_lower = query.lower()
    
    # Detect health domains
    domains = []
    if any(word in query_lower for word in ["sleep", "rest", "bed", "wake"]):
        domains.append("sleep")
    if any(word in query_lower for word in ["step", "walk", "run", "exercise", "workout", "activity"]):
        domains.append("activity")
    if any(word in query_lower for word in ["heart", "hrv", "pulse", "bpm"]):
        domains.append("heart")
    if any(word in query_lower for word in ["weight", "bmi", "body"]):
        domains.append("body")
    if any(word in query_lower for word in ["calorie", "food", "eat", "nutrition"]):
        domains.append("nutrition")
    
    # Detect time range
    last_n_days = 30  # default
    if "week" in query_lower:
        last_n_days = 7
    elif "month" in query_lower:
        last_n_days = 30
    elif "year" in query_lower:
        last_n_days = 365
    elif "today" in query_lower:
        last_n_days = 1
    elif "yesterday" in query_lower:
        last_n_days = 2
    
    return ClarifiedIntent(
        original_query=query,
        health_domains=domains if domains else ["general"],
        specific_metrics=[],
        time_context=TimeRange(
            range_type=TimeRangeType.RELATIVE,
            last_n_days=last_n_days,
        ),
        comparison_requested="compare" in query_lower or "vs" in query_lower,
        clarification_complete=bool(domains),
    )
