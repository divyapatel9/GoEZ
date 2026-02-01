"""
Sub-Agent Factory
Creates specialized analysis agents dynamically based on task definitions.
"""

from typing import Optional
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.prebuilt import create_react_agent
import json

from ..config import get_llm
from ..schema import AnalysisTask, SubAgentResult
from ..prompts import SUBAGENT_SYSTEM_PROMPT, MONGODB_SCHEMA_CONTEXT
from ..utils.mongo_toolkit import get_mongo_tools, get_mongodb_system_prompt


def create_analysis_agent(
    task: AnalysisTask,
    collection_name: str,
):
    """
    Create a specialized analysis agent for a specific task.
    
    This factory creates a ReAct agent with:
    - MongoDB query tools from langchain_mongodb toolkit
    - Task-specific system prompt
    - Structured output handling
    
    Args:
        task: The analysis task to execute
        collection_name: MongoDB collection name
        
    Returns:
        A configured agent executor
    """
    # Get LLM
    llm = get_llm(temperature=0.2, streaming=False)
    
    # Get MongoDB tools for this collection (requires LLM)
    tools = get_mongo_tools(collection_name, llm)
    
    # Get the MongoDB agent system prompt
    mongo_system_prompt = get_mongodb_system_prompt(top_k=10)
    
    # Add task-specific context with explicit collection name
    task_context = f"""

## IMPORTANT: MongoDB Collection Details

**Database**: health_logs
**Collection to query**: {collection_name}

You MUST query the `{collection_name}` collection for all health data operations.

## Your Specific Analysis Task

**Task ID**: {task.task_id}
**Objective**: {task.objective}
**Relevant Fields**: {', '.join(task.relevant_fields)}
**Time Range**: Last {task.time_range.last_n_days} days
**Suggested Analysis Types**: {', '.join(task.aggregation_hints)}

## Health Data Schema Context
{MONGODB_SCHEMA_CONTEXT}

## Data Structure Notes
- The `date` field is stored as a string in format "YYYY-MM-DD" (e.g., "2023-11-15")
- Steps are in `activity.steps` field
- Sleep data is in `sleep.asleep_seconds`, `sleep.sleep_hours`
- Heart rate is in `recovery.heart_rate_bpm.avg`

## Instructions

1. Use the MongoDB tools to query the `{collection_name}` collection
2. Perform the analysis described in the objective
3. Calculate relevant metrics
4. Identify any trends or anomalies
5. Note any data quality issues or missing data

When you have completed your analysis, provide a structured summary with:
- A natural language summary of your findings
- Key metrics computed
- Any trends identified
- Any anomalies detected
- Caveats about the data
"""
    
    full_prompt = mongo_system_prompt + task_context
    
    # Create ReAct agent with prompt parameter
    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=full_prompt,
    )
    
    return agent


async def run_analysis_agent(
    task: AnalysisTask,
    collection_name: str,
) -> SubAgentResult:
    """
    Run a single analysis agent for a task.
    
    Args:
        task: The analysis task
        collection_name: MongoDB collection name
        
    Returns:
        SubAgentResult with analysis findings
    """
    try:
        # Create the agent
        agent = create_analysis_agent(task, collection_name)
        
        # Prepare the input
        input_message = f"""Execute this analysis task:

**Objective**: {task.objective}
**Fields to examine**: {', '.join(task.relevant_fields)}
**Time period**: Last {task.time_range.last_n_days} days
**Analysis types**: {', '.join(task.aggregation_hints)}

Query the data, perform the analysis, and provide your findings."""

        # Run the agent
        result = await agent.ainvoke({
            "messages": [HumanMessage(content=input_message)]
        })
        
        # Extract the final response
        messages = result.get("messages", [])
        final_response = ""
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and msg.content:
                final_response = msg.content
                break
        
        # Parse the response into structured result
        return parse_agent_response(task, final_response)
        
    except Exception as e:
        return SubAgentResult(
            task_id=task.task_id,
            objective=task.objective,
            summary=f"Analysis failed: {str(e)}",
            key_metrics={},
            trends=[],
            anomalies=[],
            supporting_data=[],
            caveats=[f"Error during analysis: {str(e)}"],
            success=False,
            error=str(e),
        )


def parse_agent_response(task: AnalysisTask, response: str) -> SubAgentResult:
    """
    Parse agent response into structured SubAgentResult.
    
    Args:
        task: The original task
        response: Agent's response string
        
    Returns:
        Structured SubAgentResult
    """
    # Try to extract JSON if present
    key_metrics = {}
    trends = []
    anomalies = []
    caveats = []
    
    # Look for JSON blocks in response
    if "```json" in response:
        try:
            json_start = response.find("```json") + 7
            json_end = response.find("```", json_start)
            json_str = response[json_start:json_end].strip()
            data = json.loads(json_str)
            
            if isinstance(data, dict):
                key_metrics = data.get("key_metrics", data.get("metrics", {}))
                trends = data.get("trends", [])
                anomalies = data.get("anomalies", [])
                caveats = data.get("caveats", [])
        except (json.JSONDecodeError, ValueError):
            pass
    
    # Extract metrics from text if not found in JSON
    if not key_metrics:
        key_metrics = extract_metrics_from_text(response)
    
    # Extract caveats from text
    if not caveats:
        caveats = extract_caveats_from_text(response)
    
    return SubAgentResult(
        task_id=task.task_id,
        objective=task.objective,
        summary=response[:1000] if len(response) > 1000 else response,
        key_metrics=key_metrics,
        trends=trends,
        anomalies=anomalies,
        supporting_data=[],
        caveats=caveats,
        success=True,
        error=None,
    )


def extract_metrics_from_text(text: str) -> dict:
    """
    Extract numerical metrics from text response.
    
    Args:
        text: Response text to parse
        
    Returns:
        Dictionary of extracted metrics
    """
    import re
    
    metrics = {}
    
    # Common patterns for metric extraction
    patterns = [
        r"average[:\s]+([0-9,.]+)",
        r"avg[:\s]+([0-9,.]+)",
        r"mean[:\s]+([0-9,.]+)",
        r"total[:\s]+([0-9,.]+)",
        r"minimum[:\s]+([0-9,.]+)",
        r"min[:\s]+([0-9,.]+)",
        r"maximum[:\s]+([0-9,.]+)",
        r"max[:\s]+([0-9,.]+)",
        r"([0-9,.]+)\s*steps",
        r"([0-9,.]+)\s*hours?\s*of\s*sleep",
        r"([0-9,.]+)\s*bpm",
        r"hrv[:\s]+([0-9,.]+)",
    ]
    
    text_lower = text.lower()
    
    for pattern in patterns:
        matches = re.findall(pattern, text_lower)
        if matches:
            # Extract the key from pattern
            key = pattern.split("[")[0].strip("\\").replace(":", "").strip()
            if key:
                try:
                    value = float(matches[0].replace(",", ""))
                    metrics[key] = value
                except ValueError:
                    pass
    
    return metrics


def extract_caveats_from_text(text: str) -> list:
    """
    Extract caveats and limitations from text.
    
    Args:
        text: Response text
        
    Returns:
        List of caveat strings
    """
    caveats = []
    
    caveat_indicators = [
        "missing data",
        "no data",
        "limited data",
        "not available",
        "could not find",
        "caveat",
        "limitation",
        "note that",
        "keep in mind",
        "however",
    ]
    
    sentences = text.replace("\n", " ").split(".")
    
    for sentence in sentences:
        sentence_lower = sentence.lower().strip()
        for indicator in caveat_indicators:
            if indicator in sentence_lower and len(sentence.strip()) > 10:
                caveats.append(sentence.strip())
                break
    
    return caveats[:5]  # Limit to 5 caveats
