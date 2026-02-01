"""
Chart Registry - Defines chart scopes and question boundaries.

Each chart has:
- chart_id: unique identifier
- display_name: human-readable name
- allowed_topics: what AI can discuss
- disallowed_topics: explicit boundaries
- required_context_endpoints: data sources needed
- quick_questions: suggested starter questions
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ChartCategory(str, Enum):
    recovery = "recovery"
    strain = "strain"
    heart = "heart"
    activity = "activity"
    composition = "composition"
    timeline = "timeline"
    raw = "raw"


@dataclass
class ChartScope:
    """Defines what an AI assistant can and cannot discuss for a chart."""
    
    chart_id: str
    display_name: str
    category: ChartCategory
    description: str
    
    # What the AI is allowed to discuss
    allowed_topics: list[str] = field(default_factory=list)
    
    # Explicit boundaries - AI must not cross these
    disallowed_topics: list[str] = field(default_factory=list)
    
    # Backend endpoints needed to build context
    required_endpoints: list[str] = field(default_factory=list)
    
    # Required metrics for context
    required_metrics: list[str] = field(default_factory=list)
    
    # Quick question chips for UI
    quick_questions: list[str] = field(default_factory=list)
    
    # System prompt addendum for this chart
    prompt_addendum: str = ""


# =============================================================================
# CHART REGISTRY
# =============================================================================

CHART_REGISTRY: dict[str, ChartScope] = {
    
    # -------------------------------------------------------------------------
    # 1. Recovery Gauge
    # -------------------------------------------------------------------------
    "recovery_gauge": ChartScope(
        chart_id="recovery_gauge",
        display_name="Recovery Score",
        category=ChartCategory.recovery,
        description="Daily recovery readiness based on HRV, resting HR, and prior effort",
        
        allowed_topics=[
            "Explain recovery score calculation and contributors",
            "Interpret recovery trend over selected time range",
            "Discuss HRV, resting HR, and effort impact on recovery",
            "Suggest low-risk recovery behaviors (sleep, hydration, rest)",
            "Frame training decisions as risk levels, not absolutes",
            "Compare current recovery to personal baseline",
        ],
        
        disallowed_topics=[
            "Medical diagnosis or health conditions",
            "Specific medication or supplement recommendations",
            "Definitive training clearance ('safe to run marathon')",
            "Gait analysis or movement mechanics",
            "Nutrition prescriptions or diet plans",
            "Claims about hormones, cortisol, or specific physiology",
        ],
        
        required_endpoints=["/analytics/scores"],
        required_metrics=["hrv_sdnn", "resting_heart_rate", "physical_effort_load"],
        
        quick_questions=[
            "Why is my recovery this score today?",
            "How has my recovery trended this week?",
            "What can I do to improve recovery?",
        ],
        
        prompt_addendum="""
You are discussing the Recovery Score card. Focus ONLY on:
- Recovery score value and its meaning (0-100 scale)
- Contributors: HRV impact, Resting HR impact, Prior Effort impact
- Trend direction over the time range
- Baseline comparison (above/below personal normal)

Always reference the specific numbers from the context.
Frame training suggestions as risk levels: "lower risk" vs "higher risk" days.
Never give definitive clearance for intense activities.
""",
    ),
    
    # -------------------------------------------------------------------------
    # 2. Recovery vs Strain Quadrant
    # -------------------------------------------------------------------------
    "recovery_vs_strain": ChartScope(
        chart_id="recovery_vs_strain",
        display_name="Recovery vs Strain",
        category=ChartCategory.strain,
        description="Scatter plot showing balance between recovery and daily strain",
        
        allowed_topics=[
            "Explain quadrant meanings (Balanced, Overreaching, Undertrained, Recovering)",
            "Identify user's typical quadrant placement",
            "Discuss patterns of overreaching or undertraining",
            "Suggest pacing strategies and deload concepts",
            "Compare strain levels to recovery capacity",
        ],
        
        disallowed_topics=[
            "Medical diagnosis",
            "Specific workout prescriptions",
            "Claims about overtraining syndrome diagnosis",
            "Gait or movement analysis",
        ],
        
        required_endpoints=["/analytics/recovery-vs-strain", "/analytics/scores"],
        required_metrics=["physical_effort_load", "active_energy"],
        
        quick_questions=[
            "What quadrant am I usually in?",
            "Am I overreaching too often?",
            "How can I find better balance?",
        ],
        
        prompt_addendum="""
You are discussing the Recovery vs Strain quadrant chart. Focus ONLY on:
- Quadrant placement interpretation:
  * Top-right (high recovery + high strain) = Balanced, optimal
  * Bottom-right (low recovery + high strain) = Overreaching, higher risk
  * Top-left (high recovery + low strain) = Undertrained, room to push
  * Bottom-left (low recovery + low strain) = Recovering, rest day
- Pattern frequency across the time range
- Balance and pacing suggestions

Use the quadrant counts from context. Never diagnose overtraining syndrome.
""",
    ),
    
    # -------------------------------------------------------------------------
    # 3. HRV + Resting HR Trend
    # -------------------------------------------------------------------------
    "hrv_rhr_trend": ChartScope(
        chart_id="hrv_rhr_trend",
        display_name="HRV & Resting HR Trend",
        category=ChartCategory.heart,
        description="Dual-axis chart showing heart rate variability and resting heart rate over time",
        
        allowed_topics=[
            "Explain what HRV and resting HR indicate about recovery",
            "Discuss divergence patterns (HRV down + RHR up = stress signal)",
            "Compare to personal baseline ranges",
            "Suggest general recovery behaviors (sleep, stress management)",
            "Explain day-to-day variability as normal",
        ],
        
        disallowed_topics=[
            "Diagnosis of heart conditions or arrhythmias",
            "Claims about specific hormones or neurotransmitters",
            "Medical advice about heart health",
            "Medication recommendations",
        ],
        
        required_endpoints=["/analytics/metric/daily"],
        required_metrics=["hrv_sdnn", "resting_heart_rate"],
        
        quick_questions=[
            "What does my HRV trend mean?",
            "Why is my resting HR elevated?",
            "Are these values normal for me?",
        ],
        
        prompt_addendum="""
You are discussing the HRV & Resting HR trend chart. Focus ONLY on:
- HRV values in milliseconds (higher generally indicates better recovery)
- Resting HR in BPM (lower generally indicates better cardiovascular fitness)
- Divergence patterns: HRV dropping while RHR rises suggests accumulated stress
- Baseline comparisons using the p25-p75 range as "normal" for this user
- Day-to-day variation is normal; focus on multi-day trends

Never diagnose heart conditions. Phrase observations as patterns, not medical findings.
""",
    ),
    
    # -------------------------------------------------------------------------
    # 4. Effort Composition
    # -------------------------------------------------------------------------
    "effort_composition": ChartScope(
        chart_id="effort_composition",
        display_name="Effort Composition",
        category=ChartCategory.composition,
        description="Stacked breakdown of what contributed to daily effort",
        
        allowed_topics=[
            "Explain which components drove effort (steps, exercise, flights, energy)",
            "Compare proportions across time periods",
            "Identify dominant effort sources",
            "Suggest simple behavior adjustments",
        ],
        
        disallowed_topics=[
            "Training clearance decisions",
            "Workout programming",
            "Calorie or nutrition advice",
            "Medical recommendations",
        ],
        
        required_endpoints=["/analytics/effort-composition"],
        required_metrics=["steps", "flights_climbed", "active_energy", "exercise_time"],
        
        quick_questions=[
            "What drove my effort today?",
            "Am I mostly active from exercise or daily movement?",
            "How does my effort composition compare over time?",
        ],
        
        prompt_addendum="""
You are discussing the Effort Composition chart. Focus ONLY on:
- Component breakdown: steps, flights climbed, active energy, exercise time
- Percentage contributions when available
- Patterns: Is effort mostly from structured exercise or daily movement?
- Simple observations about activity mix

Do not make training recommendations. Focus on describing what the data shows.
""",
    ),
    
    # -------------------------------------------------------------------------
    # 5. Readiness Timeline
    # -------------------------------------------------------------------------
    "readiness_timeline": ChartScope(
        chart_id="readiness_timeline",
        display_name="Readiness Timeline",
        category=ChartCategory.timeline,
        description="Recovery trend with annotated events explaining changes",
        
        allowed_topics=[
            "Explain why certain days have annotations",
            "Connect annotations to recovery changes",
            "Discuss patterns in recovery fluctuation",
            "Identify recurring triggers (high strain, HRV dips, RHR spikes)",
        ],
        
        disallowed_topics=[
            "Medical diagnosis of conditions",
            "Definitive cause attribution without data",
            "Treatment recommendations",
        ],
        
        required_endpoints=["/analytics/readiness-timeline", "/analytics/scores"],
        required_metrics=["hrv_sdnn", "resting_heart_rate", "physical_effort_load"],
        
        quick_questions=[
            "Why did my recovery drop on that day?",
            "What patterns explain my readiness changes?",
            "What events affected my recovery most?",
        ],
        
        prompt_addendum="""
You are discussing the Readiness Timeline. Focus ONLY on:
- Annotation explanations (high strain, HRV dip, RHR elevated, recovery up/down)
- Connecting events to recovery score changes
- Identifying recurring patterns in the data
- The timeline's story: what happened and when

Always tie explanations to specific annotated events from the context.
""",
    ),
    
    # -------------------------------------------------------------------------
    # 6. Movement Efficiency (if present)
    # -------------------------------------------------------------------------
    "movement_efficiency": ChartScope(
        chart_id="movement_efficiency",
        display_name="Movement Efficiency",
        category=ChartCategory.activity,
        description="Scatter plot of distance vs energy expenditure",
        
        allowed_topics=[
            "Explain efficiency concept (energy per distance)",
            "Identify efficient vs inefficient days",
            "Discuss factors that might affect efficiency",
        ],
        
        disallowed_topics=[
            "Gait analysis or biomechanics claims",
            "Medical conditions affecting movement",
            "Injury risk assessment",
        ],
        
        required_endpoints=["/analytics/metric/daily"],
        required_metrics=["distance_walking_running", "active_energy"],
        
        quick_questions=[
            "How efficient is my movement?",
            "What affects my movement efficiency?",
            "Am I improving over time?",
        ],
        
        prompt_addendum="""
You are discussing Movement Efficiency. Focus ONLY on:
- Energy expenditure relative to distance covered
- Days that appear more or less efficient
- General patterns without biomechanics claims

This is a simple efficiency view, not a gait analysis tool.
""",
    ),
    
    # -------------------------------------------------------------------------
    # 7. Lifestyle vs Exercise
    # -------------------------------------------------------------------------
    "lifestyle_vs_exercise": ChartScope(
        chart_id="lifestyle_vs_exercise",
        display_name="Lifestyle vs Exercise",
        category=ChartCategory.composition,
        description="Breakdown of activity sources: exercise, daily movement, standing",
        
        allowed_topics=[
            "Explain activity source breakdown",
            "Identify dominant activity type",
            "Discuss balance between structured and incidental activity",
        ],
        
        disallowed_topics=[
            "Exercise prescriptions",
            "Calorie or weight recommendations",
            "Medical advice",
        ],
        
        required_endpoints=["/analytics/effort-composition"],
        required_metrics=["steps", "exercise_time", "stand_hours"],
        
        quick_questions=[
            "Where does most of my activity come from?",
            "Am I getting enough daily movement?",
            "How balanced is my activity mix?",
        ],
        
        prompt_addendum="""
You are discussing Lifestyle vs Exercise balance. Focus ONLY on:
- Proportion from exercise vs daily steps vs standing
- Which activity type dominates
- Simple observations about activity balance

Do not prescribe exercise amounts or make weight-related comments.
""",
    ),
    
    # -------------------------------------------------------------------------
    # 8. Raw Metrics Explorer
    # -------------------------------------------------------------------------
    "raw_metrics_explorer": ChartScope(
        chart_id="raw_metrics_explorer",
        display_name="Raw Metrics Explorer",
        category=ChartCategory.raw,
        description="Advanced view of raw metric values with baseline bands",
        
        allowed_topics=[
            "Explain what the selected metric measures",
            "Interpret baseline band (p25-p75 range)",
            "Explain anomaly markers and what they indicate",
            "Teach how to read the chart",
            "Discuss data quality and coverage",
        ],
        
        disallowed_topics=[
            "Prescriptive training plans based on raw data",
            "Medical interpretation of values",
            "Diagnosis based on metric patterns",
        ],
        
        required_endpoints=["/analytics/metric/daily", "/analytics/chart-context"],
        required_metrics=[],  # Dynamic based on selected metric
        
        quick_questions=[
            "What does this metric measure?",
            "What do the baseline bands mean?",
            "Why are some days marked as anomalies?",
        ],
        
        prompt_addendum="""
You are discussing the Raw Metrics Explorer. Focus ONLY on:
- Explaining what the selected metric measures and its units
- Interpreting the baseline band as the user's normal range (p25-p75)
- Explaining that anomalies are days outside normal patterns
- Teaching chart interpretation, not making health claims

This is a data verification tool. Help users understand what they're seeing.
""",
    ),
}


def get_chart_scope(chart_id: str) -> Optional[ChartScope]:
    """Get chart scope by ID, returns None if not found."""
    return CHART_REGISTRY.get(chart_id)


def get_all_chart_ids() -> list[str]:
    """Get list of all chart IDs."""
    return list(CHART_REGISTRY.keys())


def get_charts_for_ui() -> list[dict]:
    """Get chart list formatted for UI dropdown."""
    return [
        {
            "chart_id": scope.chart_id,
            "display_name": scope.display_name,
            "category": scope.category.value,
            "quick_questions": scope.quick_questions,
        }
        for scope in CHART_REGISTRY.values()
    ]
