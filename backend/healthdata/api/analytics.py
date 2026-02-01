"""
FastAPI Analytics Endpoints

Read-only endpoints for the Apple Health analytics dashboard.
All endpoints query DuckDB tables only - no raw Parquet access.

Endpoints:
- GET /analytics/metrics - Metrics catalog
- GET /analytics/metric/daily - Daily time series with baseline
- GET /analytics/overview - Dashboard summary tiles
- GET /analytics/anomalies - Anomalies list
- GET /analytics/correlations - Correlations for a metric
- GET /analytics/chart-context - AI graph chat context
"""

from datetime import date, timedelta
from functools import lru_cache
from time import time
from typing import Optional

import duckdb
from fastapi import APIRouter, HTTPException, Query

# =============================================================================
# CACHING INFRASTRUCTURE
# =============================================================================
# Light in-memory caching for hot endpoints.
# - /analytics/metrics: 1 hour TTL (static catalog)
# - /analytics/overview: 5 minutes TTL (summary tiles)
# No caching for time series, anomalies, correlations, chart-context.

METRICS_CACHE_TTL = 3600  # 1 hour
OVERVIEW_CACHE_TTL = 300  # 5 minutes

_cache_store: dict[str, tuple[float, any]] = {}


def get_cached(key: str, ttl: int) -> Optional[any]:
    """Get value from cache if not expired."""
    if key in _cache_store:
        timestamp, value = _cache_store[key]
        if time() - timestamp < ttl:
            return value
        del _cache_store[key]
    return None


def set_cached(key: str, value: any) -> None:
    """Store value in cache with current timestamp."""
    _cache_store[key] = (time(), value)

from backend.healthdata.config import DUCKDB_PATH
from backend.healthdata.api.schemas import (
    AnomaliesResponse,
    AnomalyItem,
    AnomalyLevel,
    BaselineSummary,
    AnomalySummary,
    ChartContextResponse,
    CorrelationItem,
    CorrelationsResponse,
    DailyMetricPoint,
    DailyMetricResponse,
    DataQualityIndicators,
    MetricCategory,
    MetricInfo,
    MetricsCatalogResponse,
    OverviewResponse,
    OverviewTile,
    TimeSeriesSummary,
    TrendDirection,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])

# =============================================================================
# METRICS CATALOG (static metadata)
# =============================================================================
# This defines all known metrics with their display names and categories.
# Used by dashboard metric selector and AI graph chat.

METRICS_CATALOG: dict[str, MetricInfo] = {
    "steps": MetricInfo(
        metric_key="steps",
        display_name="Steps",
        unit="count",
        category=MetricCategory.activity,
    ),
    "active_energy": MetricInfo(
        metric_key="active_energy",
        display_name="Active Energy",
        unit="kcal",
        category=MetricCategory.activity,
    ),
    "basal_energy": MetricInfo(
        metric_key="basal_energy",
        display_name="Basal Energy",
        unit="kcal",
        category=MetricCategory.activity,
    ),
    "distance_walking_running": MetricInfo(
        metric_key="distance_walking_running",
        display_name="Distance (Walk/Run)",
        unit="km",
        category=MetricCategory.activity,
    ),
    "flights_climbed": MetricInfo(
        metric_key="flights_climbed",
        display_name="Flights Climbed",
        unit="count",
        category=MetricCategory.activity,
    ),
    "physical_effort_load": MetricInfo(
        metric_key="physical_effort_load",
        display_name="Physical Effort",
        unit="arbitrary",
        category=MetricCategory.activity,
    ),
    "exercise_time": MetricInfo(
        metric_key="exercise_time",
        display_name="Exercise Time",
        unit="min",
        category=MetricCategory.activity,
    ),
    "stand_hours": MetricInfo(
        metric_key="stand_hours",
        display_name="Stand Hours",
        unit="hours",
        category=MetricCategory.activity,
    ),
    "walking_speed": MetricInfo(
        metric_key="walking_speed",
        display_name="Walking Speed",
        unit="km/hr",
        category=MetricCategory.activity,
    ),
    "walking_step_length": MetricInfo(
        metric_key="walking_step_length",
        display_name="Step Length",
        unit="cm",
        category=MetricCategory.activity,
    ),
    "heart_rate_mean": MetricInfo(
        metric_key="heart_rate_mean",
        display_name="Heart Rate (Avg)",
        unit="bpm",
        category=MetricCategory.recovery,
    ),
    "heart_rate_min": MetricInfo(
        metric_key="heart_rate_min",
        display_name="Heart Rate (Min)",
        unit="bpm",
        category=MetricCategory.recovery,
    ),
    "heart_rate_max": MetricInfo(
        metric_key="heart_rate_max",
        display_name="Heart Rate (Max)",
        unit="bpm",
        category=MetricCategory.recovery,
    ),
    "resting_heart_rate": MetricInfo(
        metric_key="resting_heart_rate",
        display_name="Resting Heart Rate",
        unit="bpm",
        category=MetricCategory.recovery,
    ),
    "hrv_sdnn": MetricInfo(
        metric_key="hrv_sdnn",
        display_name="HRV (SDNN)",
        unit="ms",
        category=MetricCategory.recovery,
    ),
    "sleep_duration": MetricInfo(
        metric_key="sleep_duration",
        display_name="Sleep Duration",
        unit="minutes",
        category=MetricCategory.sleep,
        is_sparse=True,
        supports_anomalies=False,
    ),
    "vo2max": MetricInfo(
        metric_key="vo2max",
        display_name="VO2 Max",
        unit="mL/kg/min",
        category=MetricCategory.fitness,
        is_sparse=True,
        supports_anomalies=False,
        supports_correlations=False,
    ),
}


def get_db_connection() -> duckdb.DuckDBPyConnection:
    """Get a read-only DuckDB connection."""
    return duckdb.connect(str(DUCKDB_PATH), read_only=True)


def validate_metric_key(metric_key: str) -> MetricInfo:
    """Validate metric_key exists in catalog."""
    if metric_key not in METRICS_CATALOG:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown metric_key: {metric_key}. Valid keys: {list(METRICS_CATALOG.keys())}"
        )
    return METRICS_CATALOG[metric_key]


def validate_date_range(start_date: date, end_date: date) -> None:
    """Validate date range is sensible."""
    if start_date > end_date:
        raise HTTPException(
            status_code=400,
            detail=f"start_date ({start_date}) must be <= end_date ({end_date})"
        )
    if (end_date - start_date).days > 730:
        raise HTTPException(
            status_code=400,
            detail="Date range cannot exceed 2 years (730 days)"
        )


def interpret_correlation(corr: float, metric_a: str, metric_b: str, lag: int) -> str:
    """Generate human-readable interpretation of correlation."""
    strength = "strong" if abs(corr) >= 0.6 else "moderate" if abs(corr) >= 0.4 else "weak"
    direction = "positive" if corr > 0 else "negative"
    
    a_name = METRICS_CATALOG.get(metric_a, MetricInfo(
        metric_key=metric_a, display_name=metric_a, unit="", category=MetricCategory.activity
    )).display_name
    b_name = METRICS_CATALOG.get(metric_b, MetricInfo(
        metric_key=metric_b, display_name=metric_b, unit="", category=MetricCategory.activity
    )).display_name
    
    if lag == 0:
        return f"{strength.capitalize()} {direction} correlation between {a_name} and {b_name}"
    elif lag > 0:
        return f"{strength.capitalize()} {direction} correlation: {a_name} leads {b_name} by {lag} day(s)"
    else:
        return f"{strength.capitalize()} {direction} correlation: {b_name} leads {a_name} by {abs(lag)} day(s)"


# =============================================================================
# ENDPOINT 1: Metrics Catalog
# =============================================================================

@router.get("/metrics", response_model=MetricsCatalogResponse)
async def get_metrics_catalog() -> MetricsCatalogResponse:
    """
    Get the catalog of all available metrics.
    
    Used by:
    - Dashboard metric selector
    - AI graph chat metric awareness
    
    Cached for 1 hour (static catalog).
    """
    cache_key = "metrics_catalog"
    cached = get_cached(cache_key, METRICS_CACHE_TTL)
    if cached is not None:
        return cached
    
    metrics = list(METRICS_CATALOG.values())
    response = MetricsCatalogResponse(metrics=metrics, count=len(metrics))
    set_cached(cache_key, response)
    return response


# =============================================================================
# ENDPOINT 2: Daily Metric Time Series
# =============================================================================

@router.get("/metric/daily", response_model=DailyMetricResponse)
async def get_daily_metric(
    metric_key: str = Query(..., description="Metric key from catalog"),
    start_date: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date (YYYY-MM-DD)"),
) -> DailyMetricResponse:
    """
    Get daily time series for a metric with baseline bands.
    
    Returns data points ordered by date ASC.
    Missing days are NOT backfilled - nulls preserved.
    """
    metric_info = validate_metric_key(metric_key)
    validate_date_range(start_date, end_date)
    
    con = get_db_connection()
    try:
        # Query daily_metrics with LEFT JOIN to baselines and anomalies
        query = """
            SELECT 
                dm.date,
                dm.value,
                dm.unit,
                b.baseline_28d_p25 as baseline_p25,
                b.baseline_28d_p75 as baseline_p75,
                b.baseline_28d_median as baseline_median,
                COALESCE(a.anomaly_level, 'none') as anomaly_level
            FROM daily_metrics dm
            LEFT JOIN baselines b 
                ON dm.date = b.date AND dm.metric_key = b.metric_key
            LEFT JOIN anomalies a 
                ON dm.date = a.date AND dm.metric_key = a.metric_key
            WHERE dm.metric_key = ?
                AND dm.date >= ?
                AND dm.date <= ?
            ORDER BY dm.date ASC
        """
        result = con.execute(query, [metric_key, start_date, end_date]).fetchall()
        
        data = [
            DailyMetricPoint(
                date=row[0],
                value=row[1],
                unit=row[2] or metric_info.unit,
                baseline_p25=row[3],
                baseline_p75=row[4],
                baseline_median=row[5],
                anomaly_level=AnomalyLevel(row[6]) if row[6] else AnomalyLevel.none,
            )
            for row in result
        ]
        
        return DailyMetricResponse(
            metric_key=metric_key,
            display_name=metric_info.display_name,
            unit=metric_info.unit,
            start_date=start_date,
            end_date=end_date,
            data=data,
            count=len(data),
        )
    finally:
        con.close()


# =============================================================================
# ENDPOINT 3: Dashboard Overview
# =============================================================================

@router.get("/overview", response_model=OverviewResponse)
async def get_overview(
    end_date: Optional[date] = Query(None, description="As-of date (default: latest)"),
) -> OverviewResponse:
    """
    Get dashboard overview tiles for all metrics.
    
    Returns latest value, baseline comparison, and 7-day trend.
    
    Cached for 5 minutes (keyed by end_date).
    """
    # Check cache (key includes end_date for query param safety)
    cache_key = f"overview_{end_date}"
    cached = get_cached(cache_key, OVERVIEW_CACHE_TTL)
    if cached is not None:
        return cached
    
    con = get_db_connection()
    try:
        # Get latest date if not specified
        if end_date is None:
            result = con.execute("SELECT MAX(date) FROM daily_metrics").fetchone()
            end_date = result[0] if result and result[0] else date.today()
            # Update cache key with resolved date
            cache_key = f"overview_{end_date}"
        
        tiles = []
        
        for metric_key, metric_info in METRICS_CATALOG.items():
            # Get latest value
            latest_query = """
                SELECT date, value, unit
                FROM daily_metrics
                WHERE metric_key = ? AND date <= ?
                ORDER BY date DESC
                LIMIT 1
            """
            latest = con.execute(latest_query, [metric_key, end_date]).fetchone()
            
            if not latest:
                continue
            
            latest_date, latest_value, unit = latest
            
            # Get baseline for latest date
            baseline_query = """
                SELECT baseline_28d_median
                FROM baselines
                WHERE metric_key = ? AND date = ?
            """
            baseline = con.execute(baseline_query, [metric_key, latest_date]).fetchone()
            baseline_median = baseline[0] if baseline else None
            
            # Calculate delta vs baseline
            delta_vs_baseline = None
            delta_percent = None
            if baseline_median and latest_value is not None:
                delta_vs_baseline = latest_value - baseline_median
                if baseline_median != 0:
                    delta_percent = (delta_vs_baseline / baseline_median) * 100
            
            # Get 7-day trend
            trend_query = """
                SELECT value
                FROM daily_metrics
                WHERE metric_key = ? 
                    AND date > ? - INTERVAL 7 DAY
                    AND date <= ?
                ORDER BY date ASC
            """
            trend_data = con.execute(trend_query, [metric_key, latest_date, latest_date]).fetchall()
            
            trend_7d = TrendDirection.flat
            if len(trend_data) >= 2:
                first_val = trend_data[0][0]
                last_val = trend_data[-1][0]
                if first_val and last_val:
                    change = last_val - first_val
                    threshold = abs(first_val) * 0.05  # 5% threshold
                    if change > threshold:
                        trend_7d = TrendDirection.up
                    elif change < -threshold:
                        trend_7d = TrendDirection.down
            
            # Get anomaly level for latest date
            anomaly_query = """
                SELECT anomaly_level
                FROM anomalies
                WHERE metric_key = ? AND date = ?
            """
            anomaly = con.execute(anomaly_query, [metric_key, latest_date]).fetchone()
            anomaly_level = AnomalyLevel(anomaly[0]) if anomaly else AnomalyLevel.none
            
            tiles.append(OverviewTile(
                metric_key=metric_key,
                display_name=metric_info.display_name,
                latest_value=latest_value,
                latest_date=latest_date,
                unit=metric_info.unit,
                baseline_median=baseline_median,
                delta_vs_baseline=delta_vs_baseline,
                delta_percent=delta_percent,
                trend_7d=trend_7d,
                anomaly_level=anomaly_level,
            ))
        
        response = OverviewResponse(
            as_of_date=end_date,
            tiles=tiles,
            count=len(tiles),
        )
        set_cached(cache_key, response)
        return response
    finally:
        con.close()


# =============================================================================
# ENDPOINT 4: Anomalies List
# =============================================================================

@router.get("/anomalies", response_model=AnomaliesResponse)
async def get_anomalies(
    start_date: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date (YYYY-MM-DD)"),
    min_level: AnomalyLevel = Query(AnomalyLevel.mild, description="Minimum anomaly level"),
) -> AnomaliesResponse:
    """
    Get list of anomalies in date range.
    
    Used for timeline view, alert cards, AI insight triggers.
    """
    validate_date_range(start_date, end_date)
    
    con = get_db_connection()
    try:
        # Build level filter
        if min_level == AnomalyLevel.strong:
            level_filter = "anomaly_level = 'strong'"
        else:
            level_filter = "anomaly_level IN ('mild', 'strong')"
        
        query = f"""
            SELECT date, metric_key, value, baseline_median, anomaly_level, reason
            FROM anomalies
            WHERE date >= ? AND date <= ?
                AND {level_filter}
            ORDER BY date DESC, metric_key
        """
        result = con.execute(query, [start_date, end_date]).fetchall()
        
        anomalies = []
        for row in result:
            metric_key = row[1]
            metric_info = METRICS_CATALOG.get(metric_key)
            display_name = metric_info.display_name if metric_info else metric_key
            
            anomalies.append(AnomalyItem(
                date=row[0],
                metric_key=metric_key,
                display_name=display_name,
                value=row[2],
                baseline_median=row[3],
                anomaly_level=AnomalyLevel(row[4]),
                reason=row[5] or "",
            ))
        
        return AnomaliesResponse(
            start_date=start_date,
            end_date=end_date,
            min_level=min_level,
            anomalies=anomalies,
            count=len(anomalies),
        )
    finally:
        con.close()


# =============================================================================
# ENDPOINT 5: Correlations
# =============================================================================

@router.get("/correlations", response_model=CorrelationsResponse)
async def get_correlations(
    metric_key: str = Query(..., description="Metric key to find correlations for"),
    window_days: int = Query(90, description="Window days (default 90)"),
) -> CorrelationsResponse:
    """
    Get precomputed correlations for a metric.
    
    Returns correlations where metric_key appears as either metric_a or metric_b.
    Does NOT compute correlations on demand.
    """
    validate_metric_key(metric_key)
    
    con = get_db_connection()
    try:
        query = """
            SELECT metric_a, metric_b, lag_days, corr, n, window_days
            FROM correlations
            WHERE (metric_a = ? OR metric_b = ?)
                AND window_days = ?
            ORDER BY ABS(corr) DESC
        """
        result = con.execute(query, [metric_key, metric_key, window_days]).fetchall()
        
        correlations = []
        for row in result:
            metric_a, metric_b = row[0], row[1]
            
            a_info = METRICS_CATALOG.get(metric_a)
            b_info = METRICS_CATALOG.get(metric_b)
            
            correlations.append(CorrelationItem(
                metric_a=metric_a,
                metric_b=metric_b,
                metric_a_display=a_info.display_name if a_info else metric_a,
                metric_b_display=b_info.display_name if b_info else metric_b,
                lag_days=row[2],
                corr=round(row[3], 3),
                n=row[4],
                interpretation=interpret_correlation(row[3], metric_a, metric_b, row[2]),
            ))
        
        return CorrelationsResponse(
            metric_key=metric_key,
            window_days=window_days,
            correlations=correlations,
            count=len(correlations),
        )
    finally:
        con.close()


# =============================================================================
# ENDPOINT 6: Chart Context (for AI graph chat)
# =============================================================================

@router.get("/chart-context", response_model=ChartContextResponse)
async def get_chart_context(
    metric_key: str = Query(..., description="Metric key"),
    start_date: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date (YYYY-MM-DD)"),
    focus_date: Optional[date] = Query(None, description="Focus date for context"),
) -> ChartContextResponse:
    """
    Get structured context for AI graph chat explanations.
    
    Provides metric metadata, time series summary, baseline summary,
    anomaly summary, correlations, and data quality indicators.
    
    IMPORTANT: This endpoint prepares AI context. It does NOT call any LLM.
    """
    metric_info = validate_metric_key(metric_key)
    validate_date_range(start_date, end_date)
    
    con = get_db_connection()
    try:
        # Get time series data (last 90 points max)
        ts_query = """
            SELECT date, value
            FROM daily_metrics
            WHERE metric_key = ?
                AND date >= ?
                AND date <= ?
            ORDER BY date DESC
            LIMIT 90
        """
        ts_result = con.execute(ts_query, [metric_key, start_date, end_date]).fetchall()
        ts_result.reverse()  # Chronological order
        
        dates = [row[0] for row in ts_result]
        values = [row[1] for row in ts_result]
        non_null_values = [v for v in values if v is not None]
        
        time_series = TimeSeriesSummary(
            last_n_days=len(dates),
            values=values,
            dates=dates,
            min_value=min(non_null_values) if non_null_values else None,
            max_value=max(non_null_values) if non_null_values else None,
            mean_value=sum(non_null_values) / len(non_null_values) if non_null_values else None,
        )
        
        # Get baseline for focus_date or latest date
        baseline_date = focus_date or (dates[-1] if dates else end_date)
        baseline_query = """
            SELECT baseline_28d_median, baseline_28d_p25, baseline_28d_p75
            FROM baselines
            WHERE metric_key = ? AND date = ?
        """
        baseline_result = con.execute(baseline_query, [metric_key, baseline_date]).fetchone()
        
        baseline = BaselineSummary(
            current_median=baseline_result[0] if baseline_result else None,
            current_p25=baseline_result[1] if baseline_result else None,
            current_p75=baseline_result[2] if baseline_result else None,
            has_baseline=baseline_result is not None and baseline_result[0] is not None,
        )
        
        # Get anomalies in range
        anomaly_query = """
            SELECT date, metric_key, value, baseline_median, anomaly_level, reason
            FROM anomalies
            WHERE metric_key = ?
                AND date >= ?
                AND date <= ?
                AND anomaly_level != 'none'
            ORDER BY date DESC
            LIMIT 10
        """
        anomaly_result = con.execute(anomaly_query, [metric_key, start_date, end_date]).fetchall()
        
        recent_anomalies = [
            AnomalyItem(
                date=row[0],
                metric_key=row[1],
                display_name=metric_info.display_name,
                value=row[2],
                baseline_median=row[3],
                anomaly_level=AnomalyLevel(row[4]),
                reason=row[5] or "",
            )
            for row in anomaly_result
        ]
        
        # Count anomalies
        count_query = """
            SELECT 
                COUNT(*) FILTER (WHERE anomaly_level = 'mild') as mild,
                COUNT(*) FILTER (WHERE anomaly_level = 'strong') as strong
            FROM anomalies
            WHERE metric_key = ?
                AND date >= ?
                AND date <= ?
        """
        count_result = con.execute(count_query, [metric_key, start_date, end_date]).fetchone()
        
        anomalies = AnomalySummary(
            total_count=(count_result[0] or 0) + (count_result[1] or 0),
            mild_count=count_result[0] or 0,
            strong_count=count_result[1] or 0,
            recent_anomalies=recent_anomalies,
        )
        
        # Get correlations
        corr_query = """
            SELECT metric_a, metric_b, lag_days, corr, n
            FROM correlations
            WHERE (metric_a = ? OR metric_b = ?)
            ORDER BY ABS(corr) DESC
            LIMIT 5
        """
        corr_result = con.execute(corr_query, [metric_key, metric_key]).fetchall()
        
        correlations = [
            CorrelationItem(
                metric_a=row[0],
                metric_b=row[1],
                metric_a_display=METRICS_CATALOG.get(row[0], MetricInfo(
                    metric_key=row[0], display_name=row[0], unit="", category=MetricCategory.activity
                )).display_name,
                metric_b_display=METRICS_CATALOG.get(row[1], MetricInfo(
                    metric_key=row[1], display_name=row[1], unit="", category=MetricCategory.activity
                )).display_name,
                lag_days=row[2],
                corr=round(row[3], 3),
                n=row[4],
                interpretation=interpret_correlation(row[3], row[0], row[1], row[2]),
            )
            for row in corr_result
        ]
        
        # Data quality
        total_days = (end_date - start_date).days + 1
        days_with_data = len([v for v in values if v is not None])
        
        sample_query = """
            SELECT AVG(sample_count)
            FROM daily_metrics
            WHERE metric_key = ?
                AND date >= ?
                AND date <= ?
        """
        sample_result = con.execute(sample_query, [metric_key, start_date, end_date]).fetchone()
        
        data_quality = DataQualityIndicators(
            total_days=total_days,
            days_with_data=days_with_data,
            coverage_percent=round((days_with_data / total_days) * 100, 1) if total_days > 0 else 0,
            avg_sample_count=round(sample_result[0], 1) if sample_result and sample_result[0] else None,
        )
        
        return ChartContextResponse(
            metric_key=metric_key,
            display_name=metric_info.display_name,
            unit=metric_info.unit,
            category=metric_info.category,
            start_date=start_date,
            end_date=end_date,
            focus_date=focus_date,
            time_series=time_series,
            baseline=baseline,
            anomalies=anomalies,
            correlations=correlations,
            data_quality=data_quality,
        )
    finally:
        con.close()
