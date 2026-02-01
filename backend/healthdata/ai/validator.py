"""
Response Validator - Rule-based validation and safety filtering.

This module validates AI responses before they reach the user:
1. Blocks or rewrites dangerous content
2. Ensures evidence is grounded in context
3. Validates response structure
4. Applies safety transformations
"""

import json
import re
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class ValidationResult:
    """Result of response validation."""
    is_valid: bool
    response: dict
    warnings: list[str]
    modifications: list[str]


# =============================================================================
# BLOCKED PATTERNS
# =============================================================================

BLOCKED_PATTERNS = [
    # Diagnosis patterns
    (r"\byou have\b.*\b(disease|condition|syndrome|disorder|illness)\b", "diagnosis_claim"),
    (r"\bthis indicates\b.*\b(disease|condition|diagnosis)\b", "diagnosis_claim"),
    (r"\byou('re| are) (suffering from|diagnosed with)\b", "diagnosis_claim"),
    
    # Absolute safety claims
    (r"\b(it'?s|it is) (completely |totally |absolutely )?safe to\b", "safety_clearance"),
    (r"\byou (can|should) (definitely|absolutely|certainly) (do|go|run|exercise)\b", "safety_clearance"),
    (r"\bno risk\b", "safety_clearance"),
    (r"\bguaranteed\b", "absolute_claim"),
    
    # Medical prescriptions
    (r"\b(take|use|try) (this |these )?(medication|medicine|drug|pill)\b", "medical_prescription"),
    (r"\b(increase|decrease|change) your (dose|dosage|medication)\b", "medical_prescription"),
    (r"\byou (need|should|must) (take|use) (supplements?|vitamins?)\b", "supplement_prescription"),
    
    # Definitive claims
    (r"\bthis (definitely|certainly|absolutely|clearly) (means|shows|proves)\b", "definitive_claim"),
    (r"\bwithout a doubt\b", "definitive_claim"),
    (r"\bi('m| am) (certain|sure|positive) that\b", "definitive_claim"),
]

# Patterns to soften (not block, but transform)
SOFTENING_RULES = [
    # "You should" -> "You might consider"
    (r"\byou should\b", "you might consider"),
    # "You need to" -> "It could be helpful to"
    (r"\byou need to\b", "it could be helpful to"),
    # "Always" -> "Often" (in advice context)
    (r"\balways (do|try|make sure)\b", r"often \1"),
    # "Never" -> "Generally avoid" (in advice context)
    (r"\bnever (do|try|skip)\b", r"generally avoid \1ing"),
]


# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================

def validate_response(
    response: dict,
    context: dict,
    strict_mode: bool = True
) -> ValidationResult:
    """
    Validate and potentially modify an AI response.
    
    Args:
        response: The AI's response dict (answer, evidence, etc.)
        context: The chart context that was provided to the AI
        strict_mode: If True, block responses with serious violations
    
    Returns:
        ValidationResult with potentially modified response
    """
    warnings = []
    modifications = []
    is_valid = True
    
    # Make a copy to modify
    validated_response = response.copy()
    
    # 1. Validate structure
    structure_result = _validate_structure(validated_response)
    if not structure_result[0]:
        warnings.extend(structure_result[1])
        validated_response = _fix_structure(validated_response)
        modifications.append("Fixed response structure")
    
    # 2. Check for blocked patterns
    answer = validated_response.get("answer", "")
    for pattern, violation_type in BLOCKED_PATTERNS:
        if re.search(pattern, answer, re.IGNORECASE):
            warnings.append(f"Blocked pattern detected: {violation_type}")
            if strict_mode:
                # Rewrite the problematic section
                answer = _rewrite_violation(answer, pattern, violation_type)
                modifications.append(f"Rewrote {violation_type} content")
    
    validated_response["answer"] = answer
    
    # 3. Apply softening rules
    for old_pattern, new_text in SOFTENING_RULES:
        if re.search(old_pattern, answer, re.IGNORECASE):
            answer = re.sub(old_pattern, new_text, answer, flags=re.IGNORECASE)
            modifications.append(f"Softened language: {old_pattern}")
    
    validated_response["answer"] = answer
    
    # 4. Validate evidence grounding
    evidence = validated_response.get("evidence", [])
    key_facts = context.get("key_facts", [])
    grounded_evidence = _validate_evidence_grounding(evidence, key_facts, context)
    
    if len(grounded_evidence) < len(evidence):
        warnings.append("Some evidence items could not be verified against context")
        modifications.append("Filtered ungrounded evidence")
    
    validated_response["evidence"] = grounded_evidence if grounded_evidence else ["Based on available data"]
    
    # 5. Validate confidence alignment
    data_quality = context.get("data_quality", {})
    coverage = data_quality.get("coverage_percent", 0)
    stated_confidence = validated_response.get("confidence", "Medium")
    
    expected_confidence = _expected_confidence(coverage, context)
    if stated_confidence == "High" and expected_confidence != "High":
        validated_response["confidence"] = expected_confidence
        validated_response["confidence_reason"] = f"Adjusted: {context.get('confidence_reason', 'Data coverage limited')}"
        modifications.append(f"Adjusted confidence from High to {expected_confidence}")
    
    # 6. Ensure next_questions exist
    if not validated_response.get("next_questions"):
        validated_response["next_questions"] = _generate_default_questions(context)
        modifications.append("Added default follow-up questions")
    
    return ValidationResult(
        is_valid=is_valid,
        response=validated_response,
        warnings=warnings,
        modifications=modifications,
    )


def _validate_structure(response: dict) -> tuple[bool, list[str]]:
    """Check if response has required fields."""
    required_fields = ["answer", "evidence", "confidence", "confidence_reason", "next_questions"]
    missing = [f for f in required_fields if f not in response]
    
    if missing:
        return False, [f"Missing required field: {f}" for f in missing]
    
    # Type checks
    warnings = []
    if not isinstance(response.get("answer"), str):
        warnings.append("'answer' should be a string")
    if not isinstance(response.get("evidence"), list):
        warnings.append("'evidence' should be a list")
    if response.get("confidence") not in ["High", "Medium", "Low"]:
        warnings.append("'confidence' should be High, Medium, or Low")
    if not isinstance(response.get("next_questions"), list):
        warnings.append("'next_questions' should be a list")
    
    return len(warnings) == 0, warnings


def _fix_structure(response: dict) -> dict:
    """Fix missing or malformed structure."""
    fixed = {
        "answer": response.get("answer", str(response)),
        "evidence": response.get("evidence", []),
        "confidence": response.get("confidence", "Medium"),
        "confidence_reason": response.get("confidence_reason", "Unable to fully assess"),
        "next_questions": response.get("next_questions", []),
    }
    
    # Fix types
    if not isinstance(fixed["answer"], str):
        fixed["answer"] = str(fixed["answer"])
    if not isinstance(fixed["evidence"], list):
        fixed["evidence"] = [str(fixed["evidence"])] if fixed["evidence"] else []
    if fixed["confidence"] not in ["High", "Medium", "Low"]:
        fixed["confidence"] = "Medium"
    if not isinstance(fixed["next_questions"], list):
        fixed["next_questions"] = []
    
    return fixed


def _rewrite_violation(text: str, pattern: str, violation_type: str) -> str:
    """Rewrite text to remove violation while preserving meaning."""
    
    rewrites = {
        "diagnosis_claim": "Your data shows patterns that ",
        "safety_clearance": "Based on your data, this appears to be a ",
        "medical_prescription": "General wellness practices suggest ",
        "supplement_prescription": "Some people find it helpful to ",
        "definitive_claim": "The data suggests ",
        "absolute_claim": "Based on the available data, ",
    }
    
    # Find and replace the problematic pattern
    replacement = rewrites.get(violation_type, "The data indicates ")
    
    # Simple replacement strategy
    return re.sub(pattern, replacement, text, flags=re.IGNORECASE)


def _validate_evidence_grounding(
    evidence: list[str],
    key_facts: list[str],
    context: dict
) -> list[str]:
    """
    Validate that evidence items are grounded in the context.
    
    Returns only evidence items that can be verified.
    """
    if not evidence:
        return []
    
    grounded = []
    
    # Extract numbers from context for verification
    context_numbers = _extract_numbers_from_context(context)
    key_facts_lower = [f.lower() for f in key_facts]
    
    for item in evidence:
        if not isinstance(item, str):
            continue
            
        item_lower = item.lower()
        
        # Check if evidence is related to key facts
        is_grounded = False
        
        # Method 1: Direct key fact match
        for fact in key_facts_lower:
            if _similar_content(item_lower, fact):
                is_grounded = True
                break
        
        # Method 2: Numbers in evidence exist in context
        if not is_grounded:
            evidence_numbers = re.findall(r'\d+\.?\d*', item)
            if evidence_numbers:
                matches = sum(1 for n in evidence_numbers if float(n) in context_numbers)
                if matches >= len(evidence_numbers) * 0.5:  # At least half the numbers match
                    is_grounded = True
        
        # Method 3: Generic factual statements without specific claims
        if not is_grounded:
            # Allow generic observations that don't make specific numerical claims
            generic_patterns = [
                r"based on (the |your )?data",
                r"(shows?|indicates?|suggests?) (a |the )?pattern",
                r"over the (selected |past )?(\d+ )?(day|week|month)",
                r"compared to (your )?baseline",
            ]
            for pattern in generic_patterns:
                if re.search(pattern, item_lower):
                    is_grounded = True
                    break
        
        if is_grounded:
            grounded.append(item)
    
    return grounded


def _extract_numbers_from_context(context: dict) -> set[float]:
    """Extract all numbers from context for validation."""
    numbers = set()
    
    def extract_from_value(v: Any):
        if isinstance(v, (int, float)):
            numbers.add(float(v))
        elif isinstance(v, str):
            for match in re.findall(r'\d+\.?\d*', v):
                numbers.add(float(match))
        elif isinstance(v, dict):
            for val in v.values():
                extract_from_value(val)
        elif isinstance(v, list):
            for item in v:
                extract_from_value(item)
    
    extract_from_value(context)
    return numbers


def _similar_content(a: str, b: str) -> bool:
    """Check if two strings have similar content (fuzzy match)."""
    # Simple word overlap check
    words_a = set(re.findall(r'\w+', a.lower()))
    words_b = set(re.findall(r'\w+', b.lower()))
    
    # Remove common words
    common_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 
                   'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
                   'would', 'could', 'should', 'may', 'might', 'must', 'to',
                   'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from', 'or',
                   'and', 'but', 'if', 'your', 'you', 'this', 'that'}
    
    words_a -= common_words
    words_b -= common_words
    
    if not words_a or not words_b:
        return False
    
    overlap = len(words_a & words_b)
    return overlap >= min(3, len(words_a) * 0.5)


def _expected_confidence(coverage: float, context: dict) -> str:
    """Determine expected confidence level based on data quality."""
    if coverage >= 85:
        baselines = context.get("baselines", {})
        if baselines:
            return "High"
        return "Medium"
    elif coverage >= 50:
        return "Medium"
    else:
        return "Low"


def _generate_default_questions(context: dict) -> list[str]:
    """Generate default follow-up questions based on chart type."""
    chart_id = context.get("chart_id", "")
    
    defaults = {
        "recovery_gauge": [
            "How has my recovery trended this week?",
            "What's affecting my recovery the most?",
            "Is this recovery score typical for me?",
        ],
        "recovery_vs_strain": [
            "Am I pushing too hard?",
            "What quadrant should I aim for?",
            "How often am I overreaching?",
        ],
        "hrv_rhr_trend": [
            "Is my HRV trending in a good direction?",
            "What does the HRV/RHR divergence mean?",
            "How do I compare to my baseline?",
        ],
        "effort_composition": [
            "What drove my effort today?",
            "Am I getting enough activity variety?",
            "How do my components compare over time?",
        ],
        "readiness_timeline": [
            "What caused my recovery to change?",
            "Are there recurring patterns?",
            "What events had the biggest impact?",
        ],
        "raw_metrics_explorer": [
            "What does this metric measure?",
            "What's my normal range?",
            "Why are some days marked as anomalies?",
        ],
    }
    
    return defaults.get(chart_id, [
        "What patterns do you see in my data?",
        "How does this compare to my baseline?",
        "What should I focus on?",
    ])


# =============================================================================
# PARSE RAW LLM RESPONSE
# =============================================================================

def parse_llm_response(raw_response: str) -> dict:
    """
    Parse raw LLM response string into structured dict.
    
    Handles cases where LLM doesn't follow JSON format perfectly.
    """
    # Try direct JSON parse first
    try:
        # Look for JSON in the response
        json_match = re.search(r'\{[\s\S]*\}', raw_response)
        if json_match:
            return json.loads(json_match.group())
    except json.JSONDecodeError:
        pass
    
    # Fallback: construct response from raw text
    return {
        "answer": raw_response.strip(),
        "evidence": [],
        "confidence": "Medium",
        "confidence_reason": "Response format not structured",
        "next_questions": [],
    }


# =============================================================================
# QUICK VALIDATION HELPERS
# =============================================================================

def is_safe_response(response: dict) -> bool:
    """Quick check if response passes basic safety."""
    answer = response.get("answer", "")
    
    for pattern, _ in BLOCKED_PATTERNS:
        if re.search(pattern, answer, re.IGNORECASE):
            return False
    
    return True


def get_safety_issues(response: dict) -> list[str]:
    """Get list of safety issues in response."""
    issues = []
    answer = response.get("answer", "")
    
    for pattern, violation_type in BLOCKED_PATTERNS:
        if re.search(pattern, answer, re.IGNORECASE):
            issues.append(violation_type)
    
    return issues
