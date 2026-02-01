"""
Phase 4: Report Node
Generates the final user-facing health report.
"""

from typing import Dict, Any
from datetime import datetime
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
import json

from ..config import get_llm
from ..state import HealthAgentState
from ..schema import HealthReport, SubAgentResult, AggregatedInsights
from ..prompts import REPORT_SYSTEM_PROMPT


async def report_node(state: HealthAgentState) -> Dict[str, Any]:
    """
    Generate the final health report for the user.
    
    This node:
    1. Takes aggregated insights from Supervisor
    2. Generates a user-friendly health report
    3. Includes visualizations data and next steps
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state with final report
    """
    llm = get_llm(temperature=0.7)
    
    aggregated_insights = state.get("aggregated_insights")
    subagent_results = state.get("subagent_results", [])
    clarified_intent = state.get("clarified_intent")
    
    # Build context for report generation
    context = build_report_context(
        aggregated_insights,
        subagent_results,
        clarified_intent
    )
    
    full_prompt = f"""{REPORT_SYSTEM_PROMPT}

## Analysis Context

{context}

Generate a comprehensive but accessible health report based on this analysis.

Your report should:
1. Start with a brief executive summary
2. Present detailed findings organized by topic
3. Highlight important patterns
4. Acknowledge data limitations
5. Suggest follow-up questions

Format the report in clear Markdown for readability.

REMEMBER: Do NOT provide medical diagnoses or prescribe treatments.
Frame everything as data observations, not medical advice.
"""
    
    response = await llm.ainvoke([HumanMessage(content=full_prompt)])
    
    # Create structured report
    report_content = response.content
    report = create_health_report(
        report_content,
        aggregated_insights,
        subagent_results,
        clarified_intent
    )
    
    # Format final message for user
    final_message = format_report_message(report_content)
    
    return {
        "messages": [AIMessage(content=final_message)],
        "final_report": report,
        "current_phase": "complete",
    }


def build_report_context(
    aggregated_insights: AggregatedInsights,
    subagent_results: list,
    clarified_intent: Any
) -> str:
    """
    Build context string for report generation.
    
    Args:
        aggregated_insights: Aggregated analysis insights
        subagent_results: List of sub-agent results
        clarified_intent: User's clarified intent
        
    Returns:
        Formatted context string
    """
    context_parts = []
    
    # User's original question
    if clarified_intent:
        context_parts.append(f"**User's Question**: {clarified_intent.original_query}")
        context_parts.append(f"**Health Areas**: {', '.join(clarified_intent.health_domains)}")
        context_parts.append(f"**Time Period**: Last {clarified_intent.time_context.last_n_days} days")
    
    # Aggregated insights
    if aggregated_insights:
        context_parts.append(f"\n**Overall Summary**: {aggregated_insights.summary}")
        
        if aggregated_insights.key_findings:
            context_parts.append("\n**Key Findings**:")
            for finding in aggregated_insights.key_findings:
                context_parts.append(f"- {finding}")
        
        if aggregated_insights.cross_metric_patterns:
            context_parts.append("\n**Cross-Metric Patterns**:")
            for pattern in aggregated_insights.cross_metric_patterns:
                if isinstance(pattern, dict):
                    context_parts.append(f"- {pattern.get('pattern', str(pattern))}")
                else:
                    context_parts.append(f"- {pattern}")
        
        if aggregated_insights.correlations:
            context_parts.append("\n**Correlations**:")
            for corr in aggregated_insights.correlations:
                if isinstance(corr, dict):
                    context_parts.append(f"- {corr.get('correlation', str(corr))}")
                else:
                    context_parts.append(f"- {corr}")
        
        if aggregated_insights.data_quality_notes:
            context_parts.append("\n**Data Limitations**:")
            for note in aggregated_insights.data_quality_notes:
                context_parts.append(f"- {note}")
    
    # Individual results summary
    if subagent_results:
        context_parts.append("\n**Detailed Analysis Results**:")
        for result in subagent_results:
            if result.success:
                context_parts.append(f"\n*{result.objective}*:")
                context_parts.append(f"  Summary: {result.summary}")
                if result.key_metrics:
                    metrics_str = ", ".join(f"{k}: {v}" for k, v in list(result.key_metrics.items())[:5])
                    context_parts.append(f"  Metrics: {metrics_str}")
    
    return "\n".join(context_parts)


def create_health_report(
    report_content: str,
    aggregated_insights: AggregatedInsights,
    subagent_results: list,
    clarified_intent: Any
) -> HealthReport:
    """
    Create a structured HealthReport object.
    
    Args:
        report_content: Generated report markdown
        aggregated_insights: Aggregated insights
        subagent_results: Sub-agent results
        clarified_intent: User's intent
        
    Returns:
        HealthReport object
    """
    # Extract title from content or generate default
    title = "Health Data Analysis Report"
    if clarified_intent:
        domains = clarified_intent.health_domains
        if domains:
            title = f"{', '.join(d.title() for d in domains)} Analysis Report"
    
    # Build detailed findings
    detailed_findings = []
    for result in subagent_results:
        if result.success:
            detailed_findings.append({
                "topic": result.objective,
                "summary": result.summary,
                "metrics": result.key_metrics,
                "trends": result.trends,
                "anomalies": result.anomalies,
            })
    
    # Build visualization data
    viz_data = []
    for result in subagent_results:
        if result.success and result.key_metrics:
            viz_data.append({
                "title": result.objective,
                "type": "metrics",
                "data": result.key_metrics,
            })
        if result.success and result.trends:
            viz_data.append({
                "title": f"{result.objective} - Trends",
                "type": "trend",
                "data": result.trends,
            })
    
    # Collect caveats
    caveats = []
    if aggregated_insights:
        caveats.extend(aggregated_insights.data_quality_notes)
    caveats.append("This report is based on data analysis only and is not medical advice.")
    caveats.append("Please consult healthcare professionals for medical concerns.")
    
    # Suggest next queries
    suggested_queries = [
        "How does my weekend activity compare to weekdays?",
        "What's the relationship between my sleep and heart rate?",
        "Show me my best and worst days for exercise this month",
    ]
    
    return HealthReport(
        title=title,
        generated_at=datetime.utcnow(),
        executive_summary=aggregated_insights.summary if aggregated_insights else "Analysis complete.",
        detailed_findings=detailed_findings,
        visualizations_data=viz_data,
        caveats_and_limitations=list(set(caveats)),
        suggested_next_queries=suggested_queries,
    )


def format_report_message(report_content: str) -> str:
    """
    Format the report for display to the user.
    
    Args:
        report_content: Raw report content
        
    Returns:
        Formatted report string
    """
    # Add header
    formatted = "# 📊 Health Data Analysis Report\n\n"
    formatted += report_content
    
    # Add footer disclaimer
    formatted += "\n\n---\n"
    formatted += "*⚠️ Disclaimer: This analysis is based on your health data and is for informational purposes only. "
    formatted += "It is not medical advice. Please consult healthcare professionals for any medical concerns.*"
    
    return formatted
