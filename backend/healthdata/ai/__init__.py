"""
AI Graph Chat Module - Phase 6

Chart-grounded, persistent, safe, motivating coaching for health analytics.

Components:
- registry: Chart scopes and question boundaries
- context_builder: Deterministic context construction
- prompts: System prompts with safety guardrails
- validator: Response validation layer
- graph: LangGraph orchestrator
- api: FastAPI endpoints
"""

from .registry import CHART_REGISTRY, ChartScope
from .context_builder import build_chart_context
from .validator import validate_response

__all__ = [
    "CHART_REGISTRY",
    "ChartScope", 
    "build_chart_context",
    "validate_response",
]
