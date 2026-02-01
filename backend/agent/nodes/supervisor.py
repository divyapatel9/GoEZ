"""
Phase 3: Supervisor Node
Orchestrates sub-agent execution and aggregates results.
"""

from typing import Dict, Any, List
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
import json

from ..config import get_llm
from ..state import HealthAgentState
from ..schema import AnalysisTask, SubAgentResult, AggregatedInsights
from ..prompts import AGGREGATION_SYSTEM_PROMPT


async def supervisor_node(state: HealthAgentState) -> Dict[str, Any]:
    """
    Supervisor node that orchestrates sub-agents and aggregates results.
    
    This node:
    1. Receives analysis tasks from Brief node
    2. Dispatches sub-agents in parallel via research_executor
    3. Aggregates all results into unified insights
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state with sub-agent results and aggregated insights
    """
    from ..subagents.executor import run_parallel_analysis
    
    tasks = state.get("analysis_tasks", [])
    collection_name = state.get("collection_name", "")
    
    if not tasks:
        return {
            "messages": [AIMessage(content="No analysis tasks to execute.")],
            "subagent_results": [],
            "aggregated_insights": None,
            "current_phase": "report",
            "error": "No analysis tasks provided",
        }
    
    # Execute sub-agents in parallel
    results = await run_parallel_analysis(tasks, collection_name)
    
    # Aggregate results
    aggregated = await aggregate_results(results, tasks)
    
    # Create summary message
    successful = [r for r in results if r.success]
    failed = [r for r in results if not r.success]
    
    summary = f"Completed {len(successful)} of {len(tasks)} analysis tasks.\n\n"
    
    if successful:
        summary += "**Key Findings:**\n"
        for result in successful[:3]:  # Top 3 findings
            summary += f"- {result.summary[:100]}...\n" if len(result.summary) > 100 else f"- {result.summary}\n"
    
    if failed:
        summary += f"\n⚠️ {len(failed)} tasks encountered issues.\n"
    
    return {
        "messages": [AIMessage(content=summary)],
        "subagent_results": results,
        "aggregated_insights": aggregated,
        "current_phase": "report",
    }


async def aggregate_results(
    results: List[SubAgentResult],
    tasks: List[AnalysisTask]
) -> AggregatedInsights:
    """
    Aggregate sub-agent results into unified insights.
    
    Args:
        results: List of results from sub-agents
        tasks: Original analysis tasks
        
    Returns:
        Aggregated insights object
    """
    llm = get_llm(temperature=0.3)
    
    # Build context from results
    results_context = "## Sub-Agent Results\n\n"
    all_caveats = []
    all_metrics = {}
    
    for result in results:
        if result.success:
            results_context += f"### Task: {result.objective}\n"
            results_context += f"**Summary**: {result.summary}\n"
            
            if result.key_metrics:
                results_context += f"**Metrics**: {json.dumps(result.key_metrics, default=str)}\n"
                all_metrics.update(result.key_metrics)
            
            if result.trends:
                results_context += f"**Trends**: {json.dumps(result.trends[:3], default=str)}\n"
            
            if result.anomalies:
                results_context += f"**Anomalies**: {json.dumps(result.anomalies[:3], default=str)}\n"
            
            all_caveats.extend(result.caveats)
            results_context += "\n"
        else:
            results_context += f"### Task: {result.objective}\n"
            results_context += f"**Error**: {result.error}\n\n"
    
    # Use LLM to synthesize insights
    full_prompt = f"""{AGGREGATION_SYSTEM_PROMPT}

{results_context}

Synthesize these findings into aggregated insights. Focus on:
1. Overall patterns across all analyses
2. Cross-metric correlations or relationships
3. Most important findings to highlight
4. Data quality concerns

Respond with a JSON object:
```json
{{
    "summary": "Overall narrative of findings",
    "cross_metric_patterns": [
        {{"pattern": "description", "metrics_involved": ["metric1", "metric2"]}}
    ],
    "correlations": [
        {{"correlation": "description", "strength": "strong/moderate/weak"}}
    ],
    "key_findings": ["finding1", "finding2", "finding3"],
    "data_quality_notes": ["note1", "note2"],
    "recommendations_context": ["context1", "context2"]
}}
```
"""
    
    response = await llm.ainvoke([HumanMessage(content=full_prompt)])
    
    # Parse aggregated insights
    try:
        response_text = response.content
        if "```json" in response_text:
            json_start = response_text.find("```json") + 7
            json_end = response_text.find("```", json_start)
            json_str = response_text[json_start:json_end].strip()
        else:
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            json_str = response_text[json_start:json_end]
        
        insights_data = json.loads(json_str)
        
        return AggregatedInsights(
            summary=insights_data.get("summary", "Analysis complete."),
            cross_metric_patterns=insights_data.get("cross_metric_patterns", []),
            correlations=insights_data.get("correlations", []),
            key_findings=insights_data.get("key_findings", []),
            data_quality_notes=list(set(all_caveats + insights_data.get("data_quality_notes", []))),
            recommendations_context=insights_data.get("recommendations_context", []),
        )
    except (json.JSONDecodeError, KeyError) as e:
        # Fallback aggregation
        return create_fallback_aggregation(results, all_caveats)


def create_fallback_aggregation(
    results: List[SubAgentResult],
    caveats: List[str]
) -> AggregatedInsights:
    """
    Create a basic aggregation when LLM parsing fails.
    
    Args:
        results: Sub-agent results
        caveats: Collected caveats
        
    Returns:
        Basic AggregatedInsights
    """
    successful_results = [r for r in results if r.success]
    
    # Combine summaries
    summaries = [r.summary for r in successful_results if r.summary]
    combined_summary = " ".join(summaries) if summaries else "Analysis completed with limited results."
    
    # Extract key findings
    key_findings = []
    for result in successful_results:
        if result.key_metrics:
            for key, value in list(result.key_metrics.items())[:2]:
                key_findings.append(f"{key}: {value}")
    
    return AggregatedInsights(
        summary=combined_summary[:500],
        cross_metric_patterns=[],
        correlations=[],
        key_findings=key_findings[:5],
        data_quality_notes=list(set(caveats))[:5],
        recommendations_context=[],
    )
