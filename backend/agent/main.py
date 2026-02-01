"""
Entry Point for the Health Agent
Provides CLI interface and streaming API for the agent.
"""

import asyncio
import uuid
from typing import AsyncGenerator, Optional, Dict, Any, Union
from langchain_core.messages import HumanMessage, AIMessage

from .graph import get_health_agent_graph, create_health_agent_graph
from .state import create_initial_state
from .memory import MongoDBMemory


async def stream_health_agent(
    user_id: str,
    session_id: str,
    query: str,
    collection_name: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """
    Stream responses from the health agent.
    
    This function:
    - Loads conversation history from MongoDB
    - Streams tokens as they're generated
    - Persists state after completion
    
    Args:
        user_id: User identifier
        session_id: Session/conversation identifier
        query: User's health query
        collection_name: Optional MongoDB collection name
        
    Yields:
        String tokens as they're generated
    """
    graph = create_health_agent_graph()
    
    # Configure thread for checkpointing
    config = {
        "configurable": {
            "thread_id": session_id,
            "user_id": user_id,
        }
    }
    
    # Create initial input
    initial_state = create_initial_state(
        user_id=user_id,
        session_id=session_id,
        collection_name=collection_name,
    )
    
    # Add the user's query
    input_state = {
        **initial_state,
        "messages": [HumanMessage(content=query)],
    }
    
    # Stream events from the graph
    async for event in graph.astream_events(
        input_state,
        config=config,
        version="v2"
    ):
        event_type = event.get("event", "")
        
        # Stream LLM tokens
        if event_type == "on_chat_model_stream":
            chunk = event.get("data", {}).get("chunk")
            if chunk and hasattr(chunk, "content") and chunk.content:
                yield chunk.content
        
        # Also yield completed messages
        elif event_type == "on_chat_model_end":
            pass  # Already streamed


async def run_health_agent(
    user_id: str,
    session_id: str,
    query: str,
    collection_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run the health agent and return the complete response.
    
    Args:
        user_id: User identifier
        session_id: Session/conversation identifier
        query: User's health query
        collection_name: Optional MongoDB collection name
        
    Returns:
        Final state dictionary with all results
    """
    graph = create_health_agent_graph()
    
    config = {
        "configurable": {
            "thread_id": session_id,
            "user_id": user_id,
        }
    }
    
    initial_state = create_initial_state(
        user_id=user_id,
        session_id=session_id,
        collection_name=collection_name,
    )
    
    input_state = {
        **initial_state,
        "messages": [HumanMessage(content=query)],
    }
    
    # Run the graph
    result = await graph.ainvoke(input_state, config=config)
    
    return result


async def continue_conversation(
    user_id: str,
    session_id: str,
    message: str,
) -> AsyncGenerator[str, None]:
    """
    Continue an existing conversation with a new message.
    
    Args:
        user_id: User identifier
        session_id: Existing session ID
        message: New message from user
        
    Yields:
        String tokens as they're generated
    """
    graph = create_health_agent_graph()
    
    config = {
        "configurable": {
            "thread_id": session_id,
            "user_id": user_id,
        }
    }
    
    # Just add the new message - state will be loaded from checkpoint
    input_state = {
        "messages": [HumanMessage(content=message)],
    }
    
    async for event in graph.astream_events(
        input_state,
        config=config,
        version="v2"
    ):
        if event.get("event") == "on_chat_model_stream":
            chunk = event.get("data", {}).get("chunk")
            if chunk and hasattr(chunk, "content") and chunk.content:
                yield chunk.content


async def stream_health_agent_with_phases(
    user_id: str,
    session_id: str,
    query: str,
    collection_name: Optional[str] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Stream responses with phase tracking for frontend visualization.
    
    Yields SSE-compatible event dictionaries with:
    - phase: Phase transitions
    - token: Content tokens
    - tasks: Analysis tasks
    - subagent: Sub-agent progress
    - interrupt: Waiting for user input
    """
    import json
    
    graph = create_health_agent_graph()
    
    config = {
        "configurable": {
            "thread_id": session_id,
            "user_id": user_id,
        }
    }
    
    initial_state = create_initial_state(
        user_id=user_id,
        session_id=session_id,
        collection_name=collection_name,
    )
    
    input_state = {
        **initial_state,
        "messages": [HumanMessage(content=query)],
    }
    
    current_phase = None
    current_node = None
    
    async for event in graph.astream_events(
        input_state,
        config=config,
        version="v2"
    ):
        event_type = event.get("event", "")
        
        # Track node transitions for phase updates
        if event_type == "on_chain_start":
            node_name = event.get("name", "")
            if node_name in ["clarify", "brief", "supervisor", "report"]:
                phase_map = {
                    "clarify": "clarify",
                    "brief": "planning",
                    "supervisor": "analyzing",
                    "report": "writing",
                }
                new_phase = phase_map.get(node_name, node_name)
                if new_phase != current_phase:
                    current_phase = new_phase
                    current_node = node_name
                    yield {
                        "event": "phase",
                        "data": json.dumps({
                            "phase": current_phase,
                            "node": node_name,
                            "description": get_phase_description(current_phase)
                        })
                    }
        
        # Stream LLM tokens
        elif event_type == "on_chat_model_stream":
            chunk = event.get("data", {}).get("chunk")
            if chunk and hasattr(chunk, "content") and chunk.content:
                yield {
                    "event": "token",
                    "data": json.dumps({
                        "content": chunk.content,
                        "phase": current_phase
                    })
                }
        
        # Track chain end to capture state updates
        elif event_type == "on_chain_end":
            node_name = event.get("name", "")
            output = event.get("data", {}).get("output", {})
            
            # Emit analysis tasks when brief completes
            if node_name == "brief" and isinstance(output, dict):
                tasks = output.get("analysis_tasks", [])
                if tasks:
                    yield {
                        "event": "tasks",
                        "data": json.dumps({
                            "tasks": [
                                {"id": t.task_id, "objective": t.objective, "priority": t.priority}
                                for t in tasks
                            ]
                        })
                    }
            
            # Emit sub-agent results when supervisor completes
            elif node_name == "supervisor" and isinstance(output, dict):
                results = output.get("subagent_results", [])
                if results:
                    yield {
                        "event": "subagent",
                        "data": json.dumps({
                            "results": [
                                {
                                    "task_id": r.task_id,
                                    "summary": r.summary[:200] if r.summary else "",
                                    "success": r.success,
                                    "metrics": r.key_metrics
                                }
                                for r in results
                            ]
                        })
                    }
                
                # Also emit aggregated insights
                insights = output.get("aggregated_insights")
                if insights:
                    yield {
                        "event": "insights",
                        "data": json.dumps({
                            "summary": insights.summary,
                            "key_findings": insights.key_findings,
                            "patterns": insights.cross_metric_patterns
                        })
                    }
    
    # Check if we're in an interrupt state
    state = graph.get_state(config)
    if state.next and "wait_for_user" in state.next:
        yield {
            "event": "interrupt",
            "data": json.dumps({
                "reason": "clarification_needed",
                "session_id": session_id
            })
        }


async def continue_conversation_with_phases(
    user_id: str,
    session_id: str,
    message: str,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Continue a conversation with phase tracking (after clarification).
    """
    import json
    from langgraph.types import Command
    
    graph = create_health_agent_graph()
    
    config = {
        "configurable": {
            "thread_id": session_id,
            "user_id": user_id,
        }
    }
    
    # Check if we need to resume from interrupt
    state = graph.get_state(config)
    
    if state.next and "wait_for_user" in state.next:
        input_data = Command(resume=message)
    else:
        input_data = {"messages": [HumanMessage(content=message)]}
    
    current_phase = None
    
    async for event in graph.astream_events(
        input_data,
        config=config,
        version="v2"
    ):
        event_type = event.get("event", "")
        
        if event_type == "on_chain_start":
            node_name = event.get("name", "")
            if node_name in ["clarify", "brief", "supervisor", "report"]:
                phase_map = {
                    "clarify": "clarify",
                    "brief": "planning",
                    "supervisor": "analyzing",
                    "report": "writing",
                }
                new_phase = phase_map.get(node_name, node_name)
                if new_phase != current_phase:
                    current_phase = new_phase
                    yield {
                        "event": "phase",
                        "data": json.dumps({
                            "phase": current_phase,
                            "node": node_name,
                            "description": get_phase_description(current_phase)
                        })
                    }
        
        elif event_type == "on_chat_model_stream":
            chunk = event.get("data", {}).get("chunk")
            if chunk and hasattr(chunk, "content") and chunk.content:
                yield {
                    "event": "token",
                    "data": json.dumps({
                        "content": chunk.content,
                        "phase": current_phase
                    })
                }
        
        elif event_type == "on_chain_end":
            node_name = event.get("name", "")
            output = event.get("data", {}).get("output", {})
            
            if node_name == "brief" and isinstance(output, dict):
                tasks = output.get("analysis_tasks", [])
                if tasks:
                    yield {
                        "event": "tasks",
                        "data": json.dumps({
                            "tasks": [
                                {"id": t.task_id, "objective": t.objective, "priority": t.priority}
                                for t in tasks
                            ]
                        })
                    }
            
            elif node_name == "supervisor" and isinstance(output, dict):
                results = output.get("subagent_results", [])
                if results:
                    yield {
                        "event": "subagent",
                        "data": json.dumps({
                            "results": [
                                {
                                    "task_id": r.task_id,
                                    "summary": r.summary[:200] if r.summary else "",
                                    "success": r.success,
                                    "metrics": r.key_metrics
                                }
                                for r in results
                            ]
                        })
                    }
                
                insights = output.get("aggregated_insights")
                if insights:
                    yield {
                        "event": "insights",
                        "data": json.dumps({
                            "summary": insights.summary,
                            "key_findings": insights.key_findings,
                            "patterns": insights.cross_metric_patterns
                        })
                    }
    
    # Check for interrupt
    state = graph.get_state(config)
    if state.next and "wait_for_user" in state.next:
        yield {
            "event": "interrupt",
            "data": json.dumps({
                "reason": "clarification_needed",
                "session_id": session_id
            })
        }


def get_phase_description(phase: str) -> str:
    """Get human-readable description for a phase."""
    descriptions = {
        "clarify": "Understanding your question",
        "planning": "Planning analysis approach",
        "analyzing": "Running health data analysis",
        "writing": "Generating your health report",
        "complete": "Analysis complete",
    }
    return descriptions.get(phase, phase)


def get_session_history(user_id: str, session_id: str) -> list:
    """
    Get conversation history for a session.
    
    Args:
        user_id: User identifier
        session_id: Session identifier
        
    Returns:
        List of messages from the session
    """
    memory = MongoDBMemory(user_id=user_id)
    return memory.load_history_sync(session_id)


# ==================== CLI Interface ====================

async def cli_main():
    """Interactive CLI for the Health Agent with interrupt handling."""
    from langgraph.types import Command
    
    print("=" * 60)
    print("🏥 Personal Health Agent")
    print("=" * 60)
    print("\nAsk questions about your Apple Health data.")
    print("Type 'quit' or 'exit' to end the session.")
    print("Type 'new' to start a new conversation.\n")
    
    user_id = input("Enter your user ID (or press Enter for 'demo_user'): ").strip()
    if not user_id:
        user_id = "demo_user"
    
    session_id = str(uuid.uuid4())
    print(f"\nSession started: {session_id[:8]}...")
    print("-" * 60)
    
    graph = create_health_agent_graph()
    
    while True:
        try:
            query = input("\n📝 You: ").strip()
            
            if not query:
                continue
            
            if query.lower() in ["quit", "exit", "q"]:
                print("\n👋 Goodbye!")
                break
            
            if query.lower() == "new":
                session_id = str(uuid.uuid4())
                print(f"\n🆕 New session started: {session_id[:8]}...")
                continue
            
            config = {
                "configurable": {
                    "thread_id": session_id,
                    "user_id": user_id,
                }
            }
            
            # Check if there's an interrupted state to resume
            state = graph.get_state(config)
            
            if state.next and "wait_for_user" in state.next:
                # Resume from interrupt with user's response
                input_data = Command(resume=query)
            else:
                # Start fresh with initial state
                initial_state = create_initial_state(
                    user_id=user_id,
                    session_id=session_id,
                )
                input_data = {
                    **initial_state,
                    "messages": [HumanMessage(content=query)],
                }
            
            print("\n🤖 Health Agent: ", end="", flush=True)
            
            # Stream events from the graph
            response_printed = False
            async for event in graph.astream_events(
                input_data,
                config=config,
                version="v2"
            ):
                event_type = event.get("event", "")
                
                # Stream LLM tokens
                if event_type == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        print(chunk.content, end="", flush=True)
                        response_printed = True
            
            if response_printed:
                print()  # Newline after response
            
            # Check if graph is waiting for user input
            state = graph.get_state(config)
            if state.next and "wait_for_user" in state.next:
                # Graph is paused, waiting for clarification
                pass  # Loop will continue and get next user input
            
        except KeyboardInterrupt:
            print("\n\n👋 Interrupted. Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {str(e)}")
            import traceback
            traceback.print_exc()


def main():
    """Entry point for CLI."""
    asyncio.run(cli_main())


if __name__ == "__main__":
    main()
