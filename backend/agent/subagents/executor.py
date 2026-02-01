"""
Research Executor
Runs sub-agents in parallel and collects results.
"""

import asyncio
from typing import List
from ..schema import AnalysisTask, SubAgentResult
from ..config import settings
from .factory import run_analysis_agent


async def run_parallel_analysis(
    tasks: List[AnalysisTask],
    collection_name: str,
) -> List[SubAgentResult]:
    """
    Run multiple analysis tasks in parallel using sub-agents.
    
    This executor:
    1. Creates an agent for each task via factory
    2. Runs all agents concurrently
    3. Collects and returns all results
    
    Args:
        tasks: List of analysis tasks to execute
        collection_name: MongoDB collection for the user's data
        
    Returns:
        List of SubAgentResult objects
    """
    if not tasks:
        return []
    
    # Sort tasks by priority
    sorted_tasks = sorted(tasks, key=lambda t: t.priority)
    
    # Limit concurrent executions
    max_concurrent = min(len(sorted_tasks), settings.max_parallel_subagents)
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def run_with_semaphore(task: AnalysisTask) -> SubAgentResult:
        """Run a single task with semaphore control."""
        async with semaphore:
            try:
                return await asyncio.wait_for(
                    run_analysis_agent(task, collection_name),
                    timeout=settings.subagent_timeout_seconds
                )
            except asyncio.TimeoutError:
                return SubAgentResult(
                    task_id=task.task_id,
                    objective=task.objective,
                    summary=f"Analysis timed out after {settings.subagent_timeout_seconds} seconds",
                    key_metrics={},
                    trends=[],
                    anomalies=[],
                    supporting_data=[],
                    caveats=["Analysis timed out"],
                    success=False,
                    error="Timeout",
                )
            except Exception as e:
                return SubAgentResult(
                    task_id=task.task_id,
                    objective=task.objective,
                    summary=f"Analysis failed: {str(e)}",
                    key_metrics={},
                    trends=[],
                    anomalies=[],
                    supporting_data=[],
                    caveats=[str(e)],
                    success=False,
                    error=str(e),
                )
    
    # Run all tasks concurrently
    results = await asyncio.gather(
        *[run_with_semaphore(task) for task in sorted_tasks],
        return_exceptions=False
    )
    
    return list(results)


async def run_sequential_analysis(
    tasks: List[AnalysisTask],
    collection_name: str,
) -> List[SubAgentResult]:
    """
    Run analysis tasks sequentially (for debugging or rate limiting).
    
    Args:
        tasks: List of analysis tasks
        collection_name: MongoDB collection name
        
    Returns:
        List of SubAgentResult objects
    """
    results = []
    
    for task in tasks:
        try:
            result = await asyncio.wait_for(
                run_analysis_agent(task, collection_name),
                timeout=settings.subagent_timeout_seconds
            )
            results.append(result)
        except asyncio.TimeoutError:
            results.append(SubAgentResult(
                task_id=task.task_id,
                objective=task.objective,
                summary="Analysis timed out",
                key_metrics={},
                trends=[],
                anomalies=[],
                supporting_data=[],
                caveats=["Timeout"],
                success=False,
                error="Timeout",
            ))
        except Exception as e:
            results.append(SubAgentResult(
                task_id=task.task_id,
                objective=task.objective,
                summary=f"Error: {str(e)}",
                key_metrics={},
                trends=[],
                anomalies=[],
                supporting_data=[],
                caveats=[str(e)],
                success=False,
                error=str(e),
            ))
    
    return results
