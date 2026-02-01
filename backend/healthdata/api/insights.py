"""
Insights API Endpoints - Phase 5.5

New endpoints for WHOOP-style dashboard cards:
- GET /analytics/scores - Daily recovery and strain scores
- GET /analytics/recovery-vs-strain - Quadrant scatter data
- GET /analytics/effort-composition - Effort breakdown by component
- GET /analytics/readiness-timeline - Annotated recovery timeline

All endpoints are read-only and query pre-computed derived_scores_daily table.
No analytics computation happens in these endpoints.
"""

from datetime import date, timedelta
from enum import Enum
from typing import Optional

import duckdb
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.healthdata.config import DUCKDB_PATH

router = APIRouter(prefix="/analytics", tags=["insights"])


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class RecoveryColor(str, Enum):
    green = "green"
    yellow = "yellow"
    red = "red"


class RecoveryLabel(str, Enum):
    ready = "Ready"
    caution = "Caution"
    recover = "Recover"


class StrainLabel(str, Enum):
    high = "High"
    moderate = "Moderate"
    low = "Low"


class AnnotationType(str, Enum):
    high_strain = "high_strain"
    low_hrv = "low_hrv"
    high_rhr = "high_rhr"
    recovery_up = "recovery_up"
    recovery_down = "recovery_down"


class Contributors(BaseModel):
    hrv_pct: Optional[float] = None
    rhr_pct: Optional[float] = None
    effort_pct: Optional[float] = None


class DataQuality(BaseModel):
    total_days: int
    days_with_data: int
    coverage_percent: float


class DailyScore(BaseModel):
    date: str
    recovery_score: Optional[int] = None
    recovery_label: Optional[str] = None
    recovery_color: Optional[str] = None
    strain_score: Optional[int] = None
    strain_label: Optional[str] = None
    strain_primary_metric: Optional[str] = None
    contributors: Contributors


class ScoresResponse(BaseModel):
    start_date: str
    end_date: str
    scores: list[DailyScore]
    data_quality: DataQuality


class RecoveryStrainPoint(BaseModel):
    date: str
    recovery_score: int
    strain_score: int
    recovery_color: str


class RecoveryVsStrainResponse(BaseModel):
    start_date: str
    end_date: str
    points: list[RecoveryStrainPoint]
    count: int


class EffortBucket(BaseModel):
    period_start: str
    steps: Optional[float] = None
    flights_climbed: Optional[float] = None
    active_energy: Optional[float] = None
    exercise_time: Optional[float] = None
    heart_rate_max: Optional[float] = None
    steps_pct: Optional[float] = None
    flights_pct: Optional[float] = None
    energy_pct: Optional[float] = None
    exercise_pct: Optional[float] = None


class EffortCompositionResponse(BaseModel):
    start_date: str
    end_date: str
    granularity: str
    buckets: list[EffortBucket]
    count: int


class TimelineDay(BaseModel):
    date: str
    recovery_score: Optional[int] = None
    annotation: Optional[str] = None
    annotation_type: Optional[str] = None


class ReadinessTimelineResponse(BaseModel):
    start_date: str
    end_date: str
    timeline: list[TimelineDay]
    count: int


# =============================================================================
# HELPERS
# =============================================================================

def get_db_connection() -> duckdb.DuckDBPyConnection:
    """Get read-only DuckDB connection."""
    return duckdb.connect(str(DUCKDB_PATH), read_only=True)


def validate_date_range(start_date: date, end_date: date, max_days: int = 730):
    """Validate date range parameters."""
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date must be before end_date")
    
    delta = (end_date - start_date).days
    if delta > max_days:
        raise HTTPException(
            status_code=400,
            detail=f"Date range cannot exceed {max_days} days"
        )


# =============================================================================
# ENDPOINT 1: GET /analytics/scores
# =============================================================================

@router.get("/scores", response_model=ScoresResponse)
async def get_scores(
    start_date: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date (YYYY-MM-DD)"),
) -> ScoresResponse:
    """
    Get daily recovery and strain scores for date range.
    
    Returns pre-computed scores from derived_scores_daily table.
    Recovery uses HRV, Resting HR, and Yesterday's Effort.
    Strain uses Physical Effort Load (or Active Energy as fallback).
    """
    validate_date_range(start_date, end_date)
    
    con = get_db_connection()
    try:
        result = con.execute("""
            SELECT 
                date,
                recovery_score,
                recovery_label,
                recovery_color,
                strain_score,
                strain_label,
                strain_primary_metric,
                hrv_pct,
                rhr_pct,
                effort_pct
            FROM derived_scores_daily
            WHERE date >= ? AND date <= ?
            ORDER BY date
        """, [start_date, end_date]).fetchall()
        
        total_days = (end_date - start_date).days + 1
        days_with_recovery = sum(1 for r in result if r[1] is not None)
        days_with_strain = sum(1 for r in result if r[4] is not None)
        days_with_data = max(days_with_recovery, days_with_strain)
        
        scores = [
            DailyScore(
                date=str(row[0]),
                recovery_score=int(row[1]) if row[1] is not None else None,
                recovery_label=row[2],
                recovery_color=row[3],
                strain_score=int(row[4]) if row[4] is not None else None,
                strain_label=row[5],
                strain_primary_metric=row[6],
                contributors=Contributors(
                    hrv_pct=row[7],
                    rhr_pct=row[8],
                    effort_pct=row[9],
                ),
            )
            for row in result
        ]
        
        return ScoresResponse(
            start_date=str(start_date),
            end_date=str(end_date),
            scores=scores,
            data_quality=DataQuality(
                total_days=total_days,
                days_with_data=days_with_data,
                coverage_percent=round(100 * days_with_data / total_days, 1) if total_days > 0 else 0,
            ),
        )
    finally:
        con.close()


# =============================================================================
# ENDPOINT 2: GET /analytics/recovery-vs-strain
# =============================================================================

@router.get("/recovery-vs-strain", response_model=RecoveryVsStrainResponse)
async def get_recovery_vs_strain(
    start_date: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date (YYYY-MM-DD)"),
) -> RecoveryVsStrainResponse:
    """
    Get recovery vs strain scatter plot data.
    
    Returns only days where both scores are available.
    Used for quadrant visualization.
    """
    validate_date_range(start_date, end_date)
    
    con = get_db_connection()
    try:
        result = con.execute("""
            SELECT 
                date,
                recovery_score,
                strain_score,
                recovery_color
            FROM derived_scores_daily
            WHERE date >= ? AND date <= ?
                AND recovery_score IS NOT NULL
                AND strain_score IS NOT NULL
            ORDER BY date
        """, [start_date, end_date]).fetchall()
        
        points = [
            RecoveryStrainPoint(
                date=str(row[0]),
                recovery_score=int(row[1]),
                strain_score=int(row[2]),
                recovery_color=row[3],
            )
            for row in result
        ]
        
        return RecoveryVsStrainResponse(
            start_date=str(start_date),
            end_date=str(end_date),
            points=points,
            count=len(points),
        )
    finally:
        con.close()


# =============================================================================
# ENDPOINT 3: GET /analytics/effort-composition
# =============================================================================

@router.get("/effort-composition", response_model=EffortCompositionResponse)
async def get_effort_composition(
    start_date: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date (YYYY-MM-DD)"),
    granularity: str = Query("day", description="Aggregation: day, week, or month"),
) -> EffortCompositionResponse:
    """
    Get effort composition breakdown by component.
    
    Components: steps, flights_climbed, active_energy, exercise_time, heart_rate_max.
    Aggregated by day, week, or month.
    """
    validate_date_range(start_date, end_date)
    
    if granularity not in ["day", "week", "month"]:
        raise HTTPException(status_code=400, detail="granularity must be day, week, or month")
    
    con = get_db_connection()
    try:
        if granularity == "day":
            query = """
                SELECT 
                    date AS period_start,
                    MAX(CASE WHEN metric_key = 'steps' THEN value END) AS steps,
                    MAX(CASE WHEN metric_key = 'flights_climbed' THEN value END) AS flights_climbed,
                    MAX(CASE WHEN metric_key = 'active_energy' THEN value END) AS active_energy,
                    MAX(CASE WHEN metric_key = 'exercise_time' THEN value END) AS exercise_time,
                    MAX(CASE WHEN metric_key = 'heart_rate_max' THEN value END) AS heart_rate_max
                FROM daily_metrics
                WHERE date >= ? AND date <= ?
                    AND metric_key IN ('steps', 'flights_climbed', 'active_energy', 'exercise_time', 'heart_rate_max')
                GROUP BY date
                ORDER BY date
            """
        elif granularity == "week":
            query = """
                SELECT 
                    DATE_TRUNC('week', date) AS period_start,
                    SUM(CASE WHEN metric_key = 'steps' THEN value END) AS steps,
                    SUM(CASE WHEN metric_key = 'flights_climbed' THEN value END) AS flights_climbed,
                    SUM(CASE WHEN metric_key = 'active_energy' THEN value END) AS active_energy,
                    SUM(CASE WHEN metric_key = 'exercise_time' THEN value END) AS exercise_time,
                    MAX(CASE WHEN metric_key = 'heart_rate_max' THEN value END) AS heart_rate_max
                FROM daily_metrics
                WHERE date >= ? AND date <= ?
                    AND metric_key IN ('steps', 'flights_climbed', 'active_energy', 'exercise_time', 'heart_rate_max')
                GROUP BY DATE_TRUNC('week', date)
                ORDER BY period_start
            """
        else:  # month
            query = """
                SELECT 
                    DATE_TRUNC('month', date) AS period_start,
                    SUM(CASE WHEN metric_key = 'steps' THEN value END) AS steps,
                    SUM(CASE WHEN metric_key = 'flights_climbed' THEN value END) AS flights_climbed,
                    SUM(CASE WHEN metric_key = 'active_energy' THEN value END) AS active_energy,
                    SUM(CASE WHEN metric_key = 'exercise_time' THEN value END) AS exercise_time,
                    MAX(CASE WHEN metric_key = 'heart_rate_max' THEN value END) AS heart_rate_max
                FROM daily_metrics
                WHERE date >= ? AND date <= ?
                    AND metric_key IN ('steps', 'flights_climbed', 'active_energy', 'exercise_time', 'heart_rate_max')
                GROUP BY DATE_TRUNC('month', date)
                ORDER BY period_start
            """
        
        result = con.execute(query, [start_date, end_date]).fetchall()
        
        buckets = []
        for row in result:
            steps = row[1] or 0
            flights = row[2] or 0
            energy = row[3] or 0
            exercise = row[4] or 0
            
            total = steps + flights + energy + exercise
            if total > 0:
                steps_pct = round(100 * steps / total, 1)
                flights_pct = round(100 * flights / total, 1)
                energy_pct = round(100 * energy / total, 1)
                exercise_pct = round(100 * exercise / total, 1)
            else:
                steps_pct = flights_pct = energy_pct = exercise_pct = None
            
            buckets.append(EffortBucket(
                period_start=str(row[0]),
                steps=row[1],
                flights_climbed=row[2],
                active_energy=row[3],
                exercise_time=row[4],
                heart_rate_max=row[5],
                steps_pct=steps_pct,
                flights_pct=flights_pct,
                energy_pct=energy_pct,
                exercise_pct=exercise_pct,
            ))
        
        return EffortCompositionResponse(
            start_date=str(start_date),
            end_date=str(end_date),
            granularity=granularity,
            buckets=buckets,
            count=len(buckets),
        )
    finally:
        con.close()


# =============================================================================
# ENDPOINT 4: GET /analytics/readiness-timeline
# =============================================================================

@router.get("/readiness-timeline", response_model=ReadinessTimelineResponse)
async def get_readiness_timeline(
    start_date: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date (YYYY-MM-DD)"),
) -> ReadinessTimelineResponse:
    """
    Get recovery timeline with rule-based annotations.
    
    Annotations are purely rule-based (no AI):
    - High strain day (strong anomaly on effort/energy)
    - HRV dipped (strong anomaly, below baseline)
    - RHR elevated (strong anomaly, above baseline)
    - Recovery improved (+15 from previous day)
    - Recovery dropped (-15 from previous day)
    """
    validate_date_range(start_date, end_date)
    
    con = get_db_connection()
    try:
        result = con.execute("""
            WITH scores_with_lag AS (
                SELECT 
                    d.date,
                    d.recovery_score,
                    LAG(d.recovery_score) OVER (ORDER BY d.date) AS prev_recovery
                FROM derived_scores_daily d
                WHERE d.date >= ? AND d.date <= ?
            ),
            anomaly_check AS (
                SELECT 
                    s.date,
                    s.recovery_score,
                    s.prev_recovery,
                    -- Check for strong anomalies
                    EXISTS (
                        SELECT 1 FROM anomalies a 
                        WHERE a.date = s.date 
                        AND a.metric_key IN ('physical_effort_load', 'active_energy')
                        AND a.anomaly_level = 'strong'
                    ) AS has_strain_anomaly,
                    (
                        SELECT a.value < b.baseline_28d_median
                        FROM anomalies a
                        JOIN baselines b ON a.date = b.date AND a.metric_key = b.metric_key
                        WHERE a.date = s.date 
                        AND a.metric_key = 'hrv_sdnn'
                        AND a.anomaly_level = 'strong'
                        LIMIT 1
                    ) AS hrv_below_baseline,
                    (
                        SELECT a.value > b.baseline_28d_median
                        FROM anomalies a
                        JOIN baselines b ON a.date = b.date AND a.metric_key = b.metric_key
                        WHERE a.date = s.date 
                        AND a.metric_key = 'resting_heart_rate'
                        AND a.anomaly_level = 'strong'
                        LIMIT 1
                    ) AS rhr_above_baseline
                FROM scores_with_lag s
            )
            SELECT 
                date,
                recovery_score,
                prev_recovery,
                has_strain_anomaly,
                hrv_below_baseline,
                rhr_above_baseline
            FROM anomaly_check
            ORDER BY date
        """, [start_date, end_date]).fetchall()
        
        timeline = []
        for row in result:
            date_val = row[0]
            recovery = row[1]
            prev_recovery = row[2]
            has_strain = row[3]
            hrv_low = row[4]
            rhr_high = row[5]
            
            annotation = None
            annotation_type = None
            
            if has_strain:
                annotation = "High strain day"
                annotation_type = "high_strain"
            elif hrv_low:
                annotation = "HRV dipped below usual"
                annotation_type = "low_hrv"
            elif rhr_high:
                annotation = "Resting HR elevated"
                annotation_type = "high_rhr"
            elif recovery is not None and prev_recovery is not None:
                delta = recovery - prev_recovery
                if delta >= 15:
                    annotation = "Recovery improved"
                    annotation_type = "recovery_up"
                elif delta <= -15:
                    annotation = "Recovery dropped"
                    annotation_type = "recovery_down"
            
            timeline.append(TimelineDay(
                date=str(date_val),
                recovery_score=int(recovery) if recovery is not None else None,
                annotation=annotation,
                annotation_type=annotation_type,
            ))
        
        return ReadinessTimelineResponse(
            start_date=str(start_date),
            end_date=str(end_date),
            timeline=timeline,
            count=len(timeline),
        )
    finally:
        con.close()
