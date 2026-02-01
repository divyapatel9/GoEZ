"""
System Prompts - Safety guardrails and chart-specific instructions.

This module defines the base system prompt and chart-specific addendums.
All prompts enforce evidence-first reasoning and safety boundaries.
"""

from backend.healthdata.ai.registry import CHART_REGISTRY, get_chart_scope


# =============================================================================
# BASE SYSTEM PROMPT
# =============================================================================

BASE_SYSTEM_PROMPT = """You are a health performance intelligence coach helping users understand their health data from an Apple Health analytics dashboard. You are NOT a doctor or medical professional.

## YOUR ROLE
- Help users interpret their health metrics and patterns
- Provide friendly, motivating, evidence-based guidance
- Reference specific numbers from the provided context
- Frame suggestions in terms of risk levels, not absolutes

## CRITICAL SAFETY RULES (NEVER VIOLATE)

1. **Evidence-First**: Always cite specific data facts before giving any interpretation or suggestion. Say "Your HRV was 42ms, which is 15% below your baseline" before discussing implications.

2. **No Medical Diagnosis**: Never diagnose health conditions. Never say "you have X condition" or "this indicates Y disease."

3. **No Definitive Clearance**: Never say "it's safe to" do any activity. Instead, frame as risk levels: "Based on your recovery score, today appears to be a lower-risk day for moderate activity."

4. **No Hallucinated Physiology**: Do not make confident claims about hormones, cortisol, parasympathetic tone, or specific physiological mechanisms unless phrasing them as general concepts or hypotheses.

5. **No Made-Up Numbers**: Every number you reference MUST appear in the provided context. Never invent statistics, percentages, or values.

6. **Acknowledge Data Gaps**: If the context shows insufficient data (low coverage, missing metrics), explicitly state this and ask clarifying questions rather than guessing.

7. **No Medical Advice**: Never recommend medications, supplements, or treatments. For sleep, hydration, and general recovery behaviors, frame as "general wellness practices" not medical advice.

## RESPONSE STYLE

- Be concise and direct. Use short paragraphs.
- Be warm and supportive but not fake or overly emotional.
- Always connect observations to the user's actual data.
- When uncertain, say so clearly.
- Suggest professional guidance when appropriate (e.g., persistent concerning patterns).

## RESPONSE FORMAT

You must respond in valid JSON with this exact structure:
{
  "answer": "Your main response text here. Use clear paragraphs.",
  "evidence": ["Specific fact 1 from context", "Specific fact 2", "Specific fact 3"],
  "confidence": "High|Medium|Low",
  "confidence_reason": "Brief explanation of confidence level",
  "next_questions": ["Follow-up question 1?", "Follow-up question 2?", "Follow-up question 3?"]
}

The "evidence" array must contain 2-4 specific facts from the context that support your answer.
The "confidence" must reflect the data quality provided in context.
The "next_questions" should be relevant follow-up questions the user might want to ask.

## DISALLOWED PHRASES (NEVER USE)

- "You have [condition]"
- "This definitely means"
- "You should definitely"
- "It's safe to"
- "I guarantee"
- "This proves"
- "You need to see a doctor" (instead: "If this pattern persists, consulting a healthcare provider could be helpful")
"""


# =============================================================================
# CHART-SPECIFIC PROMPT BUILDER
# =============================================================================

def build_system_prompt(chart_id: str) -> str:
    """
    Build complete system prompt for a chart scope.
    
    Combines base prompt with chart-specific addendum.
    """
    scope = get_chart_scope(chart_id)
    
    if not scope:
        return BASE_SYSTEM_PROMPT + "\n\n## CURRENT CHART\nUnknown chart. Provide general guidance based on available context."
    
    # Build chart-specific section
    chart_section = f"""
## CURRENT CHART: {scope.display_name}

{scope.description}

### ALLOWED TOPICS
You may discuss:
{chr(10).join(f'- {topic}' for topic in scope.allowed_topics)}

### DISALLOWED TOPICS
You must NOT discuss:
{chr(10).join(f'- {topic}' for topic in scope.disallowed_topics)}

If the user asks about a disallowed topic, politely redirect them to an appropriate chart or explain that this falls outside your scope.

### CHART-SPECIFIC GUIDANCE
{scope.prompt_addendum}
"""
    
    return BASE_SYSTEM_PROMPT + chart_section


def build_context_prompt(context_dict: dict) -> str:
    """
    Build the context section that gets injected into the conversation.
    
    This formats the chart context as a clear reference for the AI.
    """
    return f"""## DATA CONTEXT

This is the authoritative data context. All numbers in your response must come from this context.

```json
{_format_context_for_prompt(context_dict)}
```

**Data Quality Assessment:**
- Coverage: {context_dict.get('data_quality', {}).get('coverage_percent', 0):.0f}% of days have data
- Confidence Level: {context_dict.get('confidence_level', 'Unknown')}
- Reason: {context_dict.get('confidence_reason', 'Not assessed')}

**Key Facts (use these in your response):**
{chr(10).join(f'- {fact}' for fact in context_dict.get('key_facts', []))}
"""


def _format_context_for_prompt(context_dict: dict) -> str:
    """Format context dict as compact JSON for prompt inclusion."""
    import json
    
    # Create a simplified view for the prompt (not full series data)
    simplified = {
        "chart_id": context_dict.get("chart_id"),
        "display_name": context_dict.get("display_name"),
        "date_range": context_dict.get("date_range"),
        "focus_date": context_dict.get("focus_date"),
        "key_facts": context_dict.get("key_facts", []),
        "data_quality": context_dict.get("data_quality"),
        "baselines": context_dict.get("baselines", {}),
        "anomalies": {
            "count": context_dict.get("anomalies", {}).get("count", 0),
        },
        "contributors": context_dict.get("contributors"),
        "confidence_level": context_dict.get("confidence_level"),
    }
    
    # Add series summary (not full data)
    series = context_dict.get("series_data", {})
    if "quadrant_counts" in series:
        simplified["quadrant_summary"] = series["quadrant_counts"]
    if "trend_7d" in series:
        simplified["trend_7d"] = series["trend_7d"]
    if "average" in series:
        simplified["average"] = series["average"]
    if "totals" in series:
        simplified["totals"] = series["totals"]
    if "stats" in series:
        simplified["stats"] = series["stats"]
    
    return json.dumps(simplified, indent=2, default=str)


# =============================================================================
# OUT-OF-SCOPE REDIRECT TEMPLATES
# =============================================================================

REDIRECT_TEMPLATES = {
    "medical": """I understand you're asking about {topic}, but that falls into medical territory that I'm not qualified to address. 

What I can help with is interpreting your health metrics and patterns. If you have specific medical concerns, consulting with a healthcare provider would be the best path forward.

Is there something about your current chart data I can help explain?""",

    "wrong_chart": """That's a great question, but it's better suited for the {suggested_chart} view rather than {current_chart}.

The {current_chart} focuses on {current_focus}. Would you like me to explain what I can see in this current view, or would you prefer to switch to {suggested_chart}?""",

    "insufficient_data": """I'd love to help with that question, but I'm seeing limited data coverage ({coverage}%) for the selected time range.

To give you accurate insights, I'd need more complete data. Here are some options:
1. Expand the date range to include more days
2. Check if this metric is being tracked consistently
3. Focus on a different metric with better coverage

What would you like to try?""",
}


def get_redirect_response(
    redirect_type: str,
    **kwargs
) -> dict:
    """
    Get a formatted redirect response when user asks out-of-scope question.
    """
    template = REDIRECT_TEMPLATES.get(redirect_type, REDIRECT_TEMPLATES["medical"])
    
    return {
        "answer": template.format(**kwargs),
        "evidence": [],
        "confidence": "High",
        "confidence_reason": "Redirect to appropriate scope",
        "next_questions": kwargs.get("suggested_questions", [
            "What does my current chart show?",
            "How should I interpret my baseline?",
            "What patterns do you see in my data?",
        ])
    }


# =============================================================================
# HIGH-RISK QUERY DETECTION
# =============================================================================

HIGH_RISK_KEYWORDS = [
    # Activity clearance
    "safe to run", "safe to exercise", "can i run", "can i workout",
    "should i run", "marathon", "race tomorrow", "competition",
    
    # Medical symptoms
    "chest pain", "heart attack", "fainting", "dizzy", "shortness of breath",
    "palpitations", "irregular heartbeat", "pass out", "blackout",
    
    # Medical conditions
    "diagnose", "diagnosis", "disease", "condition", "syndrome",
    "arrhythmia", "heart condition", "heart disease",
    
    # Treatment
    "medication", "medicine", "drug", "supplement", "prescription",
    "treatment", "cure", "therapy",
]

HIGH_RISK_RESPONSE_TEMPLATE = """I want to help, but I need to be careful here because your question touches on {risk_area}.

**What your data shows:**
{data_summary}

**Important context:**
Rather than giving you a definitive answer about {specific_concern}, I'd frame it this way:
- Your current data suggests {data_interpretation}
- This is {risk_framing}

**My recommendation:**
{recommendation}

Remember, I'm an analytics assistant, not a medical professional. For questions about {risk_area}, consulting with a healthcare provider is always the best approach."""


def check_high_risk_query(user_message: str) -> tuple[bool, str, str]:
    """
    Check if user query contains high-risk elements.
    
    Returns:
        (is_high_risk, risk_area, specific_concern)
    """
    message_lower = user_message.lower()
    
    for keyword in HIGH_RISK_KEYWORDS:
        if keyword in message_lower:
            # Categorize the risk
            if any(w in keyword for w in ["safe", "run", "exercise", "workout", "marathon", "race"]):
                return True, "exercise safety", keyword
            elif any(w in keyword for w in ["chest", "heart", "faint", "dizzy", "breath", "palpitation"]):
                return True, "physical symptoms", keyword
            elif any(w in keyword for w in ["diagnose", "disease", "condition", "syndrome", "arrhythmia"]):
                return True, "medical diagnosis", keyword
            elif any(w in keyword for w in ["medication", "medicine", "drug", "supplement", "prescription"]):
                return True, "medications and supplements", keyword
            else:
                return True, "health concerns", keyword
    
    return False, "", ""


def build_high_risk_response(
    risk_area: str,
    specific_concern: str,
    context_dict: dict
) -> dict:
    """
    Build a safe response for high-risk queries.
    """
    key_facts = context_dict.get("key_facts", [])
    data_summary = "\n".join(f"- {fact}" for fact in key_facts[:3]) if key_facts else "- Limited data available for assessment"
    
    confidence = context_dict.get("confidence_level", "Medium")
    
    # Risk-specific framing
    if "exercise" in risk_area:
        data_interpretation = "a data snapshot, not a clearance assessment"
        risk_framing = "information to consider alongside how you feel physically"
        recommendation = "Listen to your body. If something feels off, rest is usually the lower-risk choice. For important training decisions, consider consulting a coach or sports medicine professional."
    elif "symptoms" in risk_area:
        data_interpretation = "metrics that can vary for many reasons"
        risk_framing = "not sufficient for evaluating physical symptoms"
        recommendation = "Physical symptoms like these warrant attention from a healthcare provider, especially if they're new, persistent, or concerning to you."
    elif "diagnosis" in risk_area:
        data_interpretation = "patterns in your daily metrics"
        risk_framing = "not diagnostic - many factors can influence these numbers"
        recommendation = "For diagnostic questions, a healthcare provider can evaluate your full health picture, not just wearable data."
    else:
        data_interpretation = "general wellness metrics"
        risk_framing = "informational, not prescriptive"
        recommendation = "For specific health guidance, consulting with an appropriate professional is recommended."
    
    answer = HIGH_RISK_RESPONSE_TEMPLATE.format(
        risk_area=risk_area,
        data_summary=data_summary,
        specific_concern=specific_concern,
        data_interpretation=data_interpretation,
        risk_framing=risk_framing,
        recommendation=recommendation,
    )
    
    return {
        "answer": answer,
        "evidence": key_facts[:3] if key_facts else ["Insufficient data for detailed assessment"],
        "confidence": confidence,
        "confidence_reason": f"Providing cautious guidance for {risk_area} query",
        "next_questions": [
            "What does my recovery trend look like?",
            "How does today compare to my baseline?",
            "What patterns do you see in my recent data?",
        ]
    }
