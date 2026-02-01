"""
Phase 2: Brief Node
Generates analysis tasks based on clarified user intent.
"""

from typing import Dict, Any, List
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import json
import uuid

from ..config import get_llm
from ..state import HealthAgentState
from ..schema import AnalysisTask, TimeRange, TimeRangeType
from ..prompts import BRIEF_SYSTEM_PROMPT, MONGODB_SCHEMA_CONTEXT


async def brief_node(state: HealthAgentState) -> Dict[str, Any]:
    """
    Generate analysis tasks based on the clarified intent.
    
    This node:
    1. Takes the clarified intent from Phase 1
    2. Generates specific, executable analysis tasks
    3. Each task can be executed by a sub-agent
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state with analysis tasks
    """
    llm = get_llm(temperature=0.3)  # Lower temp for structured output
    
    clarified_intent = state.get("clarified_intent")
    messages = list(state["messages"])
    
    # Build context about what user wants
    intent_context = ""
    if clarified_intent:
        intent_context = f"""
## Clarified User Intent

- **Original Query**: {clarified_intent.original_query}
- **Health Domains**: {', '.join(clarified_intent.health_domains)}
- **Specific Metrics**: {', '.join(clarified_intent.specific_metrics) if clarified_intent.specific_metrics else 'Not specified'}
- **Time Range**: Last {clarified_intent.time_context.last_n_days} days
- **Comparison Requested**: {clarified_intent.comparison_requested}
- **Goal Context**: {clarified_intent.goal_context or 'None'}
"""
    else:
        # Extract from last user message if no clarified intent
        for msg in reversed(messages):
            if hasattr(msg, 'content') and isinstance(msg.content, str):
                intent_context = f"## User Query\n{msg.content}"
                break
    
    # Build the full prompt content
    full_prompt = f"""{BRIEF_SYSTEM_PROMPT}

{intent_context}

## Available Data Schema

{MONGODB_SCHEMA_CONTEXT}

Generate 2-5 specific analysis tasks that will answer the user's question.
Each task should be independently executable.

Respond with a JSON array of tasks:
```json
[
  {{
    "task_id": "t1",
    "objective": "Description of what to analyze",
    "relevant_fields": ["field.path"],
    "time_range": {{"range_type": "relative", "last_n_days": 30}},
    "aggregation_hints": ["daily_average"],
    "priority": 1
  }}
]
```
"""
    
    # Invoke LLM with HumanMessage (Gemini requires user message)
    response = await llm.ainvoke([HumanMessage(content=full_prompt)])
    
    # Parse tasks from response
    tasks = parse_analysis_tasks(response.content, clarified_intent)
    
    # Create response message
    task_summary = f"I've created {len(tasks)} analysis tasks:\n"
    for task in tasks:
        task_summary += f"- **{task.task_id}**: {task.objective}\n"
    task_summary += "\nNow running the analysis..."
    
    return {
        "messages": [AIMessage(content=task_summary)],
        "analysis_tasks": tasks,
        "current_phase": "research",
    }


def parse_analysis_tasks(
    response_text: str, 
    clarified_intent: Any = None
) -> List[AnalysisTask]:
    """
    Parse analysis tasks from LLM response.
    
    Args:
        response_text: Raw LLM response containing JSON
        clarified_intent: Optional clarified intent for defaults
        
    Returns:
        List of AnalysisTask objects
    """
    tasks = []
    
    try:
        # Extract JSON from response
        if "```json" in response_text:
            json_start = response_text.find("```json") + 7
            json_end = response_text.find("```", json_start)
            json_str = response_text[json_start:json_end].strip()
        elif "```" in response_text:
            json_start = response_text.find("```") + 3
            json_end = response_text.find("```", json_start)
            json_str = response_text[json_start:json_end].strip()
        else:
            # Try to find JSON array directly
            json_start = response_text.find("[")
            json_end = response_text.rfind("]") + 1
            json_str = response_text[json_start:json_end]
        
        tasks_data = json.loads(json_str)
        
        for task_data in tasks_data:
            # Parse time range
            time_range_data = task_data.get("time_range", {})
            time_range = TimeRange(
                range_type=TimeRangeType(time_range_data.get("range_type", "relative")),
                last_n_days=time_range_data.get("last_n_days", 30),
            )
            
            task = AnalysisTask(
                task_id=task_data.get("task_id", f"t{uuid.uuid4().hex[:6]}"),
                objective=task_data.get("objective", ""),
                relevant_fields=task_data.get("relevant_fields", []),
                time_range=time_range,
                aggregation_hints=task_data.get("aggregation_hints", []),
                priority=task_data.get("priority", 1),
            )
            tasks.append(task)
            
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        # Generate default tasks based on intent if parsing fails
        tasks = generate_fallback_tasks(clarified_intent)
    
    return tasks if tasks else generate_fallback_tasks(clarified_intent)


def generate_fallback_tasks(clarified_intent: Any = None) -> List[AnalysisTask]:
    """
    Generate fallback analysis tasks when LLM parsing fails.
    
    Args:
        clarified_intent: Optional clarified intent
        
    Returns:
        List of basic analysis tasks
    """
    tasks = []
    
    if clarified_intent:
        domains = clarified_intent.health_domains
        last_n_days = clarified_intent.time_context.last_n_days
    else:
        domains = ["activity", "sleep"]
        last_n_days = 30
    
    time_range = TimeRange(
        range_type=TimeRangeType.RELATIVE,
        last_n_days=last_n_days,
    )
    
    if "sleep" in domains:
        tasks.append(AnalysisTask(
            task_id="t_sleep",
            objective="Analyze sleep duration and quality patterns",
            relevant_fields=["sleep.asleep_seconds", "sleep.sleep_score", "sleep.stages"],
            time_range=time_range,
            aggregation_hints=["daily_average", "weekly_trend"],
            priority=1,
        ))
    
    if "activity" in domains:
        tasks.append(AnalysisTask(
            task_id="t_activity",
            objective="Analyze daily activity levels and exercise patterns",
            relevant_fields=["activity.steps", "activity.exercise_minutes", "activity.active_energy_burned_kcal"],
            time_range=time_range,
            aggregation_hints=["daily_average", "trend"],
            priority=1,
        ))
    
    if "heart" in domains:
        tasks.append(AnalysisTask(
            task_id="t_heart",
            objective="Analyze heart rate and HRV patterns",
            relevant_fields=["heart.resting_heart_rate", "heart.hrv_average_ms"],
            time_range=time_range,
            aggregation_hints=["daily_average", "anomaly_detection"],
            priority=1,
        ))
    
    if not tasks:
        # Default general health overview
        tasks.append(AnalysisTask(
            task_id="t_overview",
            objective="Provide general health data overview",
            relevant_fields=["activity.steps", "sleep.asleep_seconds", "heart.resting_heart_rate"],
            time_range=time_range,
            aggregation_hints=["daily_average", "summary"],
            priority=1,
        ))
    
    return tasks
