"""
Chart Context Builder - Deterministic context construction for AI chat.

This module builds structured JSON context for each chart type by querying
backend endpoints. NO LLM calls happen here - this is pure data retrieval
and transformation.

The context includes:
- Key facts with actual numbers
- Time series summaries
- Baseline comparisons
- Anomaly information
- Data quality indicators
- Confidence level assessment
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum
from typing import Any, Optional

import duckdb

from backend.healthdata.config import DUCKDB_PATH
from backend.healthdata.ai.registry import CHART_REGISTRY, get_chart_scope


class ConfidenceLevel(str, Enum):
    high = "High"
    medium = "Medium"
    low = "Low"


@dataclass
class DataQuality:
    total_days: int
    days_with_data: int
    coverage_percent: float
    has_required_metrics: bool = True
    missing_metrics: list[str] = field(default_factory=list)


@dataclass
class ChartContext:
    """Structured context for AI chat about a specific chart."""
    
    chart_id: str
    display_name: str
    date_range: dict[str, str]
    focus_date: Optional[str]
    
    # Data quality assessment
    data_quality: DataQuality
    
    # Key facts - short statements with numbers
    key_facts: list[str]
    
    # Chart-specific data
    series_data: dict[str, Any]
    
    # Baseline information
    baselines: dict[str, Any]
    
    # Anomaly summary
    anomalies: dict[str, Any]
    
    # Top correlations (if relevant)
    correlations: list[dict[str, Any]]
    
    # Contributors (for recovery chart)
    contributors: Optional[dict[str, Any]] = None
    
    # Confidence assessment
    confidence_level: ConfidenceLevel = ConfidenceLevel.medium
    confidence_reason: str = ""
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "chart_id": self.chart_id,
            "display_name": self.display_name,
            "date_range": self.date_range,
            "focus_date": self.focus_date,
            "data_quality": {
                "total_days": self.data_quality.total_days,
                "days_with_data": self.data_quality.days_with_data,
                "coverage_percent": self.data_quality.coverage_percent,
                "has_required_metrics": self.data_quality.has_required_metrics,
                "missing_metrics": self.data_quality.missing_metrics,
            },
            "key_facts": self.key_facts,
            "series_data": self.series_data,
            "baselines": self.baselines,
            "anomalies": self.anomalies,
            "correlations": self.correlations,
            "contributors": self.contributors,
            "confidence_level": self.confidence_level.value,
            "confidence_reason": self.confidence_reason,
        }


def get_db_connection() -> duckdb.DuckDBPyConnection:
    """Get read-only DuckDB connection."""
    return duckdb.connect(str(DUCKDB_PATH), read_only=True)


def _format_date(d: date) -> str:
    """Format date as string."""
    return d.strftime("%Y-%m-%d")


def _calculate_confidence(
    coverage: float,
    has_baselines: bool,
    has_required_metrics: bool,
    missing_metrics: list[str]
) -> tuple[ConfidenceLevel, str]:
    """
    Calculate confidence level based on data quality.
    
    High: coverage >= 85%, baselines present, all required metrics
    Medium: coverage 50-85% OR some baselines missing
    Low: coverage < 50% OR key metrics missing
    """
    reasons = []
    
    if coverage < 50:
        reasons.append(f"Low data coverage ({coverage:.0f}%)")
        return ConfidenceLevel.low, "; ".join(reasons) or "Insufficient data"
    
    if not has_required_metrics:
        reasons.append(f"Missing metrics: {', '.join(missing_metrics)}")
        return ConfidenceLevel.low, "; ".join(reasons)
    
    if coverage < 85:
        reasons.append(f"Partial data coverage ({coverage:.0f}%)")
    
    if not has_baselines:
        reasons.append("Baseline data not available")
    
    if reasons:
        return ConfidenceLevel.medium, "; ".join(reasons)
    
    return ConfidenceLevel.high, "Good data coverage with baseline comparisons available"


# =============================================================================
# RECOVERY GAUGE CONTEXT
# =============================================================================

def _build_recovery_gauge_context(
    con: duckdb.DuckDBPyConnection,
    start_date: date,
    end_date: date,
    focus_date: Optional[date]
) -> ChartContext:
    """Build context for Recovery Gauge chart."""
    
    # Get scores data
    result = con.execute("""
        SELECT 
            date, recovery_score, recovery_label, recovery_color,
            strain_score, hrv_pct, rhr_pct, effort_pct
        FROM derived_scores_daily
        WHERE date >= ? AND date <= ?
        ORDER BY date DESC
    """, [start_date, end_date]).fetchall()
    
    total_days = (end_date - start_date).days + 1
    days_with_data = sum(1 for r in result if r[1] is not None)
    coverage = (days_with_data / total_days * 100) if total_days > 0 else 0
    
    # Resolve focus date
    if focus_date is None and result:
        focus_date = result[0][0]  # Latest date with data
    
    # Get focus day data
    focus_data = None
    for row in result:
        if row[0] == focus_date:
            focus_data = {
                "date": str(row[0]),
                "recovery_score": row[1],
                "recovery_label": row[2],
                "recovery_color": row[3],
                "strain_score": row[4],
                "contributors": {
                    "hrv_pct": row[5],
                    "rhr_pct": row[6],
                    "effort_pct": row[7],
                }
            }
            break
    
    # Get baseline for recovery metrics
    baseline_result = con.execute("""
        SELECT metric_key, baseline_28d_median, baseline_28d_p25, baseline_28d_p75
        FROM baselines
        WHERE date = ? AND metric_key IN ('hrv_sdnn', 'resting_heart_rate')
    """, [focus_date or end_date]).fetchall()
    
    baselines = {}
    for row in baseline_result:
        baselines[row[0]] = {
            "median": row[1],
            "p25": row[2],
            "p75": row[3],
        }
    
    has_baselines = len(baselines) >= 2
    
    # Calculate 7-day trend
    recent_scores = [r[1] for r in result[:7] if r[1] is not None]
    trend_7d = None
    if len(recent_scores) >= 2:
        trend_7d = recent_scores[0] - recent_scores[-1]  # Latest minus oldest in window
    
    # Calculate 30-day average
    all_scores = [r[1] for r in result if r[1] is not None]
    avg_30d = sum(all_scores) / len(all_scores) if all_scores else None
    
    # Build key facts
    key_facts = []
    if focus_data and focus_data["recovery_score"]:
        score = focus_data["recovery_score"]
        label = focus_data["recovery_label"]
        key_facts.append(f"Recovery on {focus_data['date']}: {score} ({label})")
        
        if avg_30d:
            diff = score - avg_30d
            direction = "above" if diff > 0 else "below"
            key_facts.append(f"This is {abs(diff):.0f} points {direction} your {len(all_scores)}-day average of {avg_30d:.0f}")
        
        if focus_data["contributors"]["hrv_pct"] is not None:
            hrv_impact = focus_data["contributors"]["hrv_pct"]
            hrv_word = "positive" if hrv_impact > 0 else "negative"
            key_facts.append(f"HRV contributed {abs(hrv_impact):.0f}% {hrv_word} impact")
        
        if focus_data["contributors"]["rhr_pct"] is not None:
            rhr_impact = focus_data["contributors"]["rhr_pct"]
            rhr_word = "positive" if rhr_impact > 0 else "negative"
            key_facts.append(f"Resting HR contributed {abs(rhr_impact):.0f}% {rhr_word} impact")
    
    if trend_7d is not None:
        trend_word = "improved" if trend_7d > 0 else "declined"
        key_facts.append(f"7-day trend: Recovery {trend_word} by {abs(trend_7d):.0f} points")
    
    # Get anomalies
    anomaly_result = con.execute("""
        SELECT date, metric_key, anomaly_level, reason
        FROM anomalies
        WHERE date >= ? AND date <= ?
            AND metric_key IN ('hrv_sdnn', 'resting_heart_rate', 'physical_effort_load')
            AND anomaly_level != 'none'
        ORDER BY date DESC
        LIMIT 5
    """, [start_date, end_date]).fetchall()
    
    anomalies = {
        "count": len(anomaly_result),
        "recent": [
            {"date": str(r[0]), "metric": r[1], "level": r[2], "reason": r[3]}
            for r in anomaly_result
        ]
    }
    
    # Series data
    series_data = {
        "scores": [
            {"date": str(r[0]), "recovery": r[1], "strain": r[4]}
            for r in result
        ],
        "trend_7d": trend_7d,
        "average": avg_30d,
    }
    
    # Confidence
    confidence_level, confidence_reason = _calculate_confidence(
        coverage, has_baselines, True, []
    )
    
    return ChartContext(
        chart_id="recovery_gauge",
        display_name="Recovery Score",
        date_range={"start": _format_date(start_date), "end": _format_date(end_date)},
        focus_date=_format_date(focus_date) if focus_date else None,
        data_quality=DataQuality(
            total_days=total_days,
            days_with_data=days_with_data,
            coverage_percent=round(coverage, 1),
        ),
        key_facts=key_facts,
        series_data=series_data,
        baselines=baselines,
        anomalies=anomalies,
        correlations=[],
        contributors=focus_data["contributors"] if focus_data else None,
        confidence_level=confidence_level,
        confidence_reason=confidence_reason,
    )


# =============================================================================
# RECOVERY VS STRAIN CONTEXT
# =============================================================================

def _build_recovery_vs_strain_context(
    con: duckdb.DuckDBPyConnection,
    start_date: date,
    end_date: date,
    focus_date: Optional[date]
) -> ChartContext:
    """Build context for Recovery vs Strain quadrant chart."""
    
    result = con.execute("""
        SELECT date, recovery_score, strain_score, recovery_color
        FROM derived_scores_daily
        WHERE date >= ? AND date <= ?
            AND recovery_score IS NOT NULL
            AND strain_score IS NOT NULL
        ORDER BY date DESC
    """, [start_date, end_date]).fetchall()
    
    total_days = (end_date - start_date).days + 1
    days_with_data = len(result)
    coverage = (days_with_data / total_days * 100) if total_days > 0 else 0
    
    # Quadrant counts (using 50 as midpoint)
    quadrants = {
        "balanced": 0,      # High recovery, high strain (top-right)
        "overreaching": 0,  # Low recovery, high strain (bottom-right)
        "undertrained": 0,  # High recovery, low strain (top-left)
        "recovering": 0,    # Low recovery, low strain (bottom-left)
    }
    
    for row in result:
        recovery, strain = row[1], row[2]
        if recovery >= 50 and strain >= 50:
            quadrants["balanced"] += 1
        elif recovery < 50 and strain >= 50:
            quadrants["overreaching"] += 1
        elif recovery >= 50 and strain < 50:
            quadrants["undertrained"] += 1
        else:
            quadrants["recovering"] += 1
    
    # Find dominant quadrant
    dominant = max(quadrants.items(), key=lambda x: x[1])
    
    # Today's position
    today_data = None
    if result:
        today_data = {
            "date": str(result[0][0]),
            "recovery": result[0][1],
            "strain": result[0][2],
            "quadrant": (
                "balanced" if result[0][1] >= 50 and result[0][2] >= 50 else
                "overreaching" if result[0][1] < 50 and result[0][2] >= 50 else
                "undertrained" if result[0][1] >= 50 and result[0][2] < 50 else
                "recovering"
            )
        }
    
    # Key facts
    key_facts = []
    if days_with_data > 0:
        key_facts.append(f"Analyzed {days_with_data} days with both scores")
        key_facts.append(f"Most common: {dominant[0].title()} quadrant ({dominant[1]} days, {dominant[1]/days_with_data*100:.0f}%)")
        
        if quadrants["overreaching"] > 0:
            pct = quadrants["overreaching"] / days_with_data * 100
            key_facts.append(f"Overreaching (high strain + low recovery): {quadrants['overreaching']} days ({pct:.0f}%)")
        
        if today_data:
            key_facts.append(f"Latest ({today_data['date']}): Recovery {today_data['recovery']}, Strain {today_data['strain']} = {today_data['quadrant'].title()}")
    
    series_data = {
        "points": [
            {"date": str(r[0]), "recovery": r[1], "strain": r[2]}
            for r in result
        ],
        "quadrant_counts": quadrants,
        "dominant_quadrant": dominant[0],
        "today": today_data,
    }
    
    confidence_level, confidence_reason = _calculate_confidence(
        coverage, True, days_with_data > 0, []
    )
    
    return ChartContext(
        chart_id="recovery_vs_strain",
        display_name="Recovery vs Strain",
        date_range={"start": _format_date(start_date), "end": _format_date(end_date)},
        focus_date=_format_date(focus_date) if focus_date else None,
        data_quality=DataQuality(
            total_days=total_days,
            days_with_data=days_with_data,
            coverage_percent=round(coverage, 1),
        ),
        key_facts=key_facts,
        series_data=series_data,
        baselines={},
        anomalies={"count": 0, "recent": []},
        correlations=[],
        confidence_level=confidence_level,
        confidence_reason=confidence_reason,
    )


# =============================================================================
# HRV + RHR TREND CONTEXT
# =============================================================================

def _build_hrv_rhr_context(
    con: duckdb.DuckDBPyConnection,
    start_date: date,
    end_date: date,
    focus_date: Optional[date]
) -> ChartContext:
    """Build context for HRV + Resting HR trend chart."""
    
    # Get HRV data
    hrv_result = con.execute("""
        SELECT dm.date, dm.value, b.baseline_28d_median, b.baseline_28d_p25, b.baseline_28d_p75
        FROM daily_metrics dm
        LEFT JOIN baselines b ON dm.date = b.date AND dm.metric_key = b.metric_key
        WHERE dm.metric_key = 'hrv_sdnn' AND dm.date >= ? AND dm.date <= ?
        ORDER BY dm.date DESC
    """, [start_date, end_date]).fetchall()
    
    # Get RHR data
    rhr_result = con.execute("""
        SELECT dm.date, dm.value, b.baseline_28d_median, b.baseline_28d_p25, b.baseline_28d_p75
        FROM daily_metrics dm
        LEFT JOIN baselines b ON dm.date = b.date AND dm.metric_key = b.metric_key
        WHERE dm.metric_key = 'resting_heart_rate' AND dm.date >= ? AND dm.date <= ?
        ORDER BY dm.date DESC
    """, [start_date, end_date]).fetchall()
    
    total_days = (end_date - start_date).days + 1
    hrv_days = len([r for r in hrv_result if r[1] is not None])
    rhr_days = len([r for r in rhr_result if r[1] is not None])
    days_with_data = max(hrv_days, rhr_days)
    coverage = (days_with_data / total_days * 100) if total_days > 0 else 0
    
    # Latest values
    latest_hrv = hrv_result[0] if hrv_result and hrv_result[0][1] else None
    latest_rhr = rhr_result[0] if rhr_result and rhr_result[0][1] else None
    
    # Baselines
    baselines = {}
    if latest_hrv and latest_hrv[2]:
        baselines["hrv_sdnn"] = {
            "median": latest_hrv[2],
            "p25": latest_hrv[3],
            "p75": latest_hrv[4],
        }
    if latest_rhr and latest_rhr[2]:
        baselines["resting_heart_rate"] = {
            "median": latest_rhr[2],
            "p25": latest_rhr[3],
            "p75": latest_rhr[4],
        }
    
    has_baselines = len(baselines) >= 2
    
    # Key facts
    key_facts = []
    if latest_hrv and latest_hrv[1]:
        hrv_val = latest_hrv[1]
        key_facts.append(f"Latest HRV: {hrv_val:.0f} ms")
        if latest_hrv[2]:
            diff_pct = ((hrv_val - latest_hrv[2]) / latest_hrv[2]) * 100
            direction = "above" if diff_pct > 0 else "below"
            key_facts.append(f"HRV is {abs(diff_pct):.0f}% {direction} baseline ({latest_hrv[2]:.0f} ms)")
    
    if latest_rhr and latest_rhr[1]:
        rhr_val = latest_rhr[1]
        key_facts.append(f"Latest Resting HR: {rhr_val:.0f} bpm")
        if latest_rhr[2]:
            diff_pct = ((rhr_val - latest_rhr[2]) / latest_rhr[2]) * 100
            direction = "above" if diff_pct > 0 else "below"
            key_facts.append(f"Resting HR is {abs(diff_pct):.0f}% {direction} baseline ({latest_rhr[2]:.0f} bpm)")
    
    # Divergence check (HRV down + RHR up = stress signal)
    if latest_hrv and latest_hrv[1] and latest_hrv[2] and latest_rhr and latest_rhr[1] and latest_rhr[2]:
        hrv_below = latest_hrv[1] < latest_hrv[2]
        rhr_above = latest_rhr[1] > latest_rhr[2]
        if hrv_below and rhr_above:
            key_facts.append("Pattern note: HRV below baseline while RHR above baseline may indicate accumulated stress")
    
    # Get anomalies
    anomaly_result = con.execute("""
        SELECT date, metric_key, anomaly_level, reason
        FROM anomalies
        WHERE date >= ? AND date <= ?
            AND metric_key IN ('hrv_sdnn', 'resting_heart_rate')
            AND anomaly_level != 'none'
        ORDER BY date DESC
        LIMIT 5
    """, [start_date, end_date]).fetchall()
    
    series_data = {
        "hrv": [{"date": str(r[0]), "value": r[1]} for r in hrv_result],
        "rhr": [{"date": str(r[0]), "value": r[1]} for r in rhr_result],
    }
    
    anomalies = {
        "count": len(anomaly_result),
        "recent": [
            {"date": str(r[0]), "metric": r[1], "level": r[2], "reason": r[3]}
            for r in anomaly_result
        ]
    }
    
    confidence_level, confidence_reason = _calculate_confidence(
        coverage, has_baselines, hrv_days > 0 and rhr_days > 0, []
    )
    
    return ChartContext(
        chart_id="hrv_rhr_trend",
        display_name="HRV & Resting HR Trend",
        date_range={"start": _format_date(start_date), "end": _format_date(end_date)},
        focus_date=_format_date(focus_date) if focus_date else None,
        data_quality=DataQuality(
            total_days=total_days,
            days_with_data=days_with_data,
            coverage_percent=round(coverage, 1),
        ),
        key_facts=key_facts,
        series_data=series_data,
        baselines=baselines,
        anomalies=anomalies,
        correlations=[],
        confidence_level=confidence_level,
        confidence_reason=confidence_reason,
    )


# =============================================================================
# EFFORT COMPOSITION CONTEXT
# =============================================================================

def _build_effort_composition_context(
    con: duckdb.DuckDBPyConnection,
    start_date: date,
    end_date: date,
    focus_date: Optional[date]
) -> ChartContext:
    """Build context for Effort Composition chart."""
    
    result = con.execute("""
        SELECT 
            date,
            MAX(CASE WHEN metric_key = 'steps' THEN value END) AS steps,
            MAX(CASE WHEN metric_key = 'flights_climbed' THEN value END) AS flights,
            MAX(CASE WHEN metric_key = 'active_energy' THEN value END) AS energy,
            MAX(CASE WHEN metric_key = 'exercise_time' THEN value END) AS exercise
        FROM daily_metrics
        WHERE date >= ? AND date <= ?
            AND metric_key IN ('steps', 'flights_climbed', 'active_energy', 'exercise_time')
        GROUP BY date
        ORDER BY date DESC
    """, [start_date, end_date]).fetchall()
    
    total_days = (end_date - start_date).days + 1
    days_with_data = len(result)
    coverage = (days_with_data / total_days * 100) if total_days > 0 else 0
    
    # Calculate averages and totals
    total_steps = sum(r[1] or 0 for r in result)
    total_flights = sum(r[2] or 0 for r in result)
    total_energy = sum(r[3] or 0 for r in result)
    total_exercise = sum(r[4] or 0 for r in result)
    
    # Latest day
    latest = result[0] if result else None
    
    key_facts = []
    if days_with_data > 0:
        avg_steps = total_steps / days_with_data
        avg_energy = total_energy / days_with_data
        key_facts.append(f"Average daily steps: {avg_steps:,.0f}")
        key_facts.append(f"Average daily active energy: {avg_energy:,.0f} kcal")
        
        if total_flights > 0:
            avg_flights = total_flights / days_with_data
            key_facts.append(f"Average flights climbed: {avg_flights:.1f}")
    
    if latest:
        key_facts.append(f"Latest ({latest[0]}): {latest[1] or 0:,.0f} steps, {latest[3] or 0:,.0f} kcal")
    
    series_data = {
        "buckets": [
            {
                "date": str(r[0]),
                "steps": r[1],
                "flights": r[2],
                "energy": r[3],
                "exercise": r[4],
            }
            for r in result
        ],
        "totals": {
            "steps": total_steps,
            "flights": total_flights,
            "energy": total_energy,
            "exercise": total_exercise,
        },
    }
    
    confidence_level, confidence_reason = _calculate_confidence(
        coverage, True, days_with_data > 0, []
    )
    
    return ChartContext(
        chart_id="effort_composition",
        display_name="Effort Composition",
        date_range={"start": _format_date(start_date), "end": _format_date(end_date)},
        focus_date=_format_date(focus_date) if focus_date else None,
        data_quality=DataQuality(
            total_days=total_days,
            days_with_data=days_with_data,
            coverage_percent=round(coverage, 1),
        ),
        key_facts=key_facts,
        series_data=series_data,
        baselines={},
        anomalies={"count": 0, "recent": []},
        correlations=[],
        confidence_level=confidence_level,
        confidence_reason=confidence_reason,
    )


# =============================================================================
# READINESS TIMELINE CONTEXT
# =============================================================================

def _build_readiness_timeline_context(
    con: duckdb.DuckDBPyConnection,
    start_date: date,
    end_date: date,
    focus_date: Optional[date]
) -> ChartContext:
    """Build context for Readiness Timeline chart."""
    
    # Get scores with lag for change detection
    result = con.execute("""
        WITH scores_with_lag AS (
            SELECT 
                date,
                recovery_score,
                recovery_label,
                LAG(recovery_score) OVER (ORDER BY date) AS prev_recovery
            FROM derived_scores_daily
            WHERE date >= ? AND date <= ?
        )
        SELECT * FROM scores_with_lag ORDER BY date DESC
    """, [start_date, end_date]).fetchall()
    
    total_days = (end_date - start_date).days + 1
    days_with_data = sum(1 for r in result if r[1] is not None)
    coverage = (days_with_data / total_days * 100) if total_days > 0 else 0
    
    # Get annotations from anomalies
    anomaly_result = con.execute("""
        SELECT date, metric_key, anomaly_level, value, baseline_median, reason
        FROM anomalies
        WHERE date >= ? AND date <= ?
            AND metric_key IN ('hrv_sdnn', 'resting_heart_rate', 'physical_effort_load', 'active_energy')
            AND anomaly_level = 'strong'
        ORDER BY date DESC
    """, [start_date, end_date]).fetchall()
    
    # Build annotations map
    annotations_by_date = {}
    for row in anomaly_result:
        date_str = str(row[0])
        if date_str not in annotations_by_date:
            metric = row[1]
            if metric in ('physical_effort_load', 'active_energy'):
                annotations_by_date[date_str] = {"type": "high_strain", "text": "High strain day"}
            elif metric == 'hrv_sdnn' and row[3] < row[4]:
                annotations_by_date[date_str] = {"type": "low_hrv", "text": "HRV dipped"}
            elif metric == 'resting_heart_rate' and row[3] > row[4]:
                annotations_by_date[date_str] = {"type": "high_rhr", "text": "RHR elevated"}
    
    # Add recovery change annotations
    for row in result:
        if row[1] is not None and row[3] is not None:
            delta = row[1] - row[3]
            date_str = str(row[0])
            if date_str not in annotations_by_date:
                if delta >= 15:
                    annotations_by_date[date_str] = {"type": "recovery_up", "text": "Recovery improved"}
                elif delta <= -15:
                    annotations_by_date[date_str] = {"type": "recovery_down", "text": "Recovery dropped"}
    
    # Key facts
    key_facts = []
    annotation_count = len(annotations_by_date)
    key_facts.append(f"Timeline covers {days_with_data} days with {annotation_count} notable events")
    
    # Count annotation types
    type_counts = {}
    for ann in annotations_by_date.values():
        t = ann["type"]
        type_counts[t] = type_counts.get(t, 0) + 1
    
    for t, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        label = {
            "high_strain": "High strain days",
            "low_hrv": "HRV dips",
            "high_rhr": "Elevated RHR",
            "recovery_up": "Recovery improvements",
            "recovery_down": "Recovery drops",
        }.get(t, t)
        key_facts.append(f"{label}: {count}")
    
    series_data = {
        "timeline": [
            {
                "date": str(r[0]),
                "recovery": r[1],
                "label": r[2],
                "annotation": annotations_by_date.get(str(r[0])),
            }
            for r in result
        ],
        "annotation_counts": type_counts,
    }
    
    confidence_level, confidence_reason = _calculate_confidence(
        coverage, True, days_with_data > 0, []
    )
    
    return ChartContext(
        chart_id="readiness_timeline",
        display_name="Readiness Timeline",
        date_range={"start": _format_date(start_date), "end": _format_date(end_date)},
        focus_date=_format_date(focus_date) if focus_date else None,
        data_quality=DataQuality(
            total_days=total_days,
            days_with_data=days_with_data,
            coverage_percent=round(coverage, 1),
        ),
        key_facts=key_facts,
        series_data=series_data,
        baselines={},
        anomalies={"count": annotation_count, "by_type": type_counts},
        correlations=[],
        confidence_level=confidence_level,
        confidence_reason=confidence_reason,
    )


# =============================================================================
# RAW METRICS EXPLORER CONTEXT
# =============================================================================

def _build_raw_metrics_context(
    con: duckdb.DuckDBPyConnection,
    start_date: date,
    end_date: date,
    focus_date: Optional[date],
    metric_key: str
) -> ChartContext:
    """Build context for Raw Metrics Explorer chart."""
    
    # Get metric info
    metric_info = con.execute("""
        SELECT DISTINCT metric_key, unit FROM daily_metrics WHERE metric_key = ?
    """, [metric_key]).fetchone()
    
    if not metric_info:
        return ChartContext(
            chart_id="raw_metrics_explorer",
            display_name=f"Raw Metrics: {metric_key}",
            date_range={"start": _format_date(start_date), "end": _format_date(end_date)},
            focus_date=None,
            data_quality=DataQuality(total_days=0, days_with_data=0, coverage_percent=0, has_required_metrics=False, missing_metrics=[metric_key]),
            key_facts=[f"Metric '{metric_key}' not found"],
            series_data={},
            baselines={},
            anomalies={"count": 0, "recent": []},
            correlations=[],
            confidence_level=ConfidenceLevel.low,
            confidence_reason=f"Metric '{metric_key}' not found in database",
        )
    
    # Get data with baseline
    result = con.execute("""
        SELECT 
            dm.date, dm.value, dm.unit,
            b.baseline_28d_median, b.baseline_28d_p25, b.baseline_28d_p75,
            COALESCE(a.anomaly_level, 'none') as anomaly_level
        FROM daily_metrics dm
        LEFT JOIN baselines b ON dm.date = b.date AND dm.metric_key = b.metric_key
        LEFT JOIN anomalies a ON dm.date = a.date AND dm.metric_key = a.metric_key
        WHERE dm.metric_key = ? AND dm.date >= ? AND dm.date <= ?
        ORDER BY dm.date DESC
    """, [metric_key, start_date, end_date]).fetchall()
    
    total_days = (end_date - start_date).days + 1
    days_with_data = len([r for r in result if r[1] is not None])
    coverage = (days_with_data / total_days * 100) if total_days > 0 else 0
    
    # Statistics
    values = [r[1] for r in result if r[1] is not None]
    min_val = min(values) if values else None
    max_val = max(values) if values else None
    avg_val = sum(values) / len(values) if values else None
    
    # Latest baseline
    latest_baseline = None
    for r in result:
        if r[3] is not None:
            latest_baseline = {"median": r[3], "p25": r[4], "p75": r[5]}
            break
    
    # Anomaly count
    anomaly_count = len([r for r in result if r[6] != 'none'])
    
    unit = metric_info[1] or ""
    
    key_facts = []
    if days_with_data > 0:
        key_facts.append(f"Metric: {metric_key} ({unit})")
        key_facts.append(f"Range: {min_val:.1f} to {max_val:.1f} {unit}")
        key_facts.append(f"Average: {avg_val:.1f} {unit}")
        
        if latest_baseline:
            key_facts.append(f"Baseline median: {latest_baseline['median']:.1f} {unit}")
            key_facts.append(f"Normal range (p25-p75): {latest_baseline['p25']:.1f} to {latest_baseline['p75']:.1f} {unit}")
        
        if anomaly_count > 0:
            key_facts.append(f"Anomalies detected: {anomaly_count} days")
    
    series_data = {
        "values": [
            {"date": str(r[0]), "value": r[1], "anomaly": r[6]}
            for r in result
        ],
        "stats": {"min": min_val, "max": max_val, "avg": avg_val},
    }
    
    baselines = {}
    if latest_baseline:
        baselines[metric_key] = latest_baseline
    
    confidence_level, confidence_reason = _calculate_confidence(
        coverage, latest_baseline is not None, days_with_data > 0, []
    )
    
    return ChartContext(
        chart_id="raw_metrics_explorer",
        display_name=f"Raw Metrics: {metric_key}",
        date_range={"start": _format_date(start_date), "end": _format_date(end_date)},
        focus_date=_format_date(focus_date) if focus_date else None,
        data_quality=DataQuality(
            total_days=total_days,
            days_with_data=days_with_data,
            coverage_percent=round(coverage, 1),
        ),
        key_facts=key_facts,
        series_data=series_data,
        baselines=baselines,
        anomalies={"count": anomaly_count, "recent": []},
        correlations=[],
        confidence_level=confidence_level,
        confidence_reason=confidence_reason,
    )


# =============================================================================
# GENERIC CONTEXT (fallback for other charts)
# =============================================================================

def _build_generic_context(
    con: duckdb.DuckDBPyConnection,
    chart_id: str,
    start_date: date,
    end_date: date,
    focus_date: Optional[date]
) -> ChartContext:
    """Build generic context for charts without specialized builders."""
    
    scope = get_chart_scope(chart_id)
    display_name = scope.display_name if scope else chart_id
    
    return ChartContext(
        chart_id=chart_id,
        display_name=display_name,
        date_range={"start": _format_date(start_date), "end": _format_date(end_date)},
        focus_date=_format_date(focus_date) if focus_date else None,
        data_quality=DataQuality(total_days=0, days_with_data=0, coverage_percent=0),
        key_facts=["Context builder not yet implemented for this chart"],
        series_data={},
        baselines={},
        anomalies={"count": 0, "recent": []},
        correlations=[],
        confidence_level=ConfidenceLevel.low,
        confidence_reason="Specialized context builder not available",
    )


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def build_chart_context(
    chart_id: str,
    start_date: date,
    end_date: date,
    focus_date: Optional[date] = None,
    metric_key: Optional[str] = None,
) -> ChartContext:
    """
    Build structured context for AI chat about a specific chart.
    
    This is the main entry point for context building.
    NO LLM calls happen here - this is pure data retrieval.
    
    Args:
        chart_id: ID of the chart to build context for
        start_date: Start of date range
        end_date: End of date range
        focus_date: Optional specific date to focus on
        metric_key: Optional metric key (for raw_metrics_explorer)
    
    Returns:
        ChartContext with all relevant data for AI chat
    """
    con = get_db_connection()
    try:
        if chart_id == "recovery_gauge":
            return _build_recovery_gauge_context(con, start_date, end_date, focus_date)
        elif chart_id == "recovery_vs_strain":
            return _build_recovery_vs_strain_context(con, start_date, end_date, focus_date)
        elif chart_id == "hrv_rhr_trend":
            return _build_hrv_rhr_context(con, start_date, end_date, focus_date)
        elif chart_id == "effort_composition":
            return _build_effort_composition_context(con, start_date, end_date, focus_date)
        elif chart_id == "readiness_timeline":
            return _build_readiness_timeline_context(con, start_date, end_date, focus_date)
        elif chart_id == "raw_metrics_explorer":
            if not metric_key:
                metric_key = "steps"  # Default metric
            return _build_raw_metrics_context(con, start_date, end_date, focus_date, metric_key)
        else:
            return _build_generic_context(con, chart_id, start_date, end_date, focus_date)
    finally:
        con.close()
