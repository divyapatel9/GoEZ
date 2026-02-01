"""
Pydantic response models for analytics API endpoints.
All models are read-only and aligned for chart consumption.
"""

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class MetricCategory(str, Enum):
    """Categories for health metrics."""
    activity = "activity"
    recovery = "recovery"
    sleep = "sleep"
    fitness = "fitness"


class AnomalyLevel(str, Enum):
    """Anomaly severity levels."""
    none = "none"
    mild = "mild"
    strong = "strong"


class TrendDirection(str, Enum):
    """Trend direction for overview tiles."""
    up = "up"
    down = "down"
    flat = "flat"


# =============================================================================
# 1. Metrics Catalog
# =============================================================================

class MetricInfo(BaseModel):
    """Single metric metadata for catalog."""
    metric_key: str
    display_name: str
    unit: str
    category: MetricCategory
    is_sparse: bool = False
    supports_anomalies: bool = True
    supports_correlations: bool = True


class MetricsCatalogResponse(BaseModel):
    """Response for GET /analytics/metrics."""
    metrics: list[MetricInfo]
    count: int


# =============================================================================
# 2. Daily Metric Time Series
# =============================================================================

class DailyMetricPoint(BaseModel):
    """Single data point for time series chart."""
    date: date
    value: Optional[float] = None
    unit: str
    baseline_p25: Optional[float] = None
    baseline_p75: Optional[float] = None
    baseline_median: Optional[float] = None
    anomaly_level: AnomalyLevel = AnomalyLevel.none


class DailyMetricResponse(BaseModel):
    """Response for GET /analytics/metric/daily."""
    metric_key: str
    display_name: str
    unit: str
    start_date: date
    end_date: date
    data: list[DailyMetricPoint]
    count: int


# =============================================================================
# 3. Dashboard Overview
# =============================================================================

class OverviewTile(BaseModel):
    """Single metric tile for dashboard overview."""
    metric_key: str
    display_name: str
    latest_value: Optional[float] = None
    latest_date: Optional[date] = None
    unit: str
    baseline_median: Optional[float] = None
    delta_vs_baseline: Optional[float] = None
    delta_percent: Optional[float] = None
    trend_7d: TrendDirection = TrendDirection.flat
    anomaly_level: AnomalyLevel = AnomalyLevel.none


class OverviewResponse(BaseModel):
    """Response for GET /analytics/overview."""
    as_of_date: date
    tiles: list[OverviewTile]
    count: int


# =============================================================================
# 4. Anomalies List
# =============================================================================

class AnomalyItem(BaseModel):
    """Single anomaly record."""
    date: date
    metric_key: str
    display_name: str
    value: float
    baseline_median: Optional[float] = None
    anomaly_level: AnomalyLevel
    reason: str


class AnomaliesResponse(BaseModel):
    """Response for GET /analytics/anomalies."""
    start_date: date
    end_date: date
    min_level: AnomalyLevel
    anomalies: list[AnomalyItem]
    count: int


# =============================================================================
# 5. Correlations
# =============================================================================

class CorrelationItem(BaseModel):
    """Single correlation record."""
    metric_a: str
    metric_b: str
    metric_a_display: str
    metric_b_display: str
    lag_days: int
    corr: float
    n: int
    interpretation: str = Field(
        description="Human-readable interpretation of correlation"
    )


class CorrelationsResponse(BaseModel):
    """Response for GET /analytics/correlations."""
    metric_key: str
    window_days: int
    correlations: list[CorrelationItem]
    count: int


# =============================================================================
# 6. Chart Context (for AI graph chat)
# =============================================================================

class TimeSeriesSummary(BaseModel):
    """Summary of recent time series data."""
    last_n_days: int
    values: list[Optional[float]]
    dates: list[date]
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    mean_value: Optional[float] = None


class BaselineSummary(BaseModel):
    """Summary of baseline statistics."""
    current_median: Optional[float] = None
    current_p25: Optional[float] = None
    current_p75: Optional[float] = None
    has_baseline: bool = False


class AnomalySummary(BaseModel):
    """Summary of anomalies in the period."""
    total_count: int = 0
    mild_count: int = 0
    strong_count: int = 0
    recent_anomalies: list[AnomalyItem] = []


class DataQualityIndicators(BaseModel):
    """Data quality metrics for the period."""
    total_days: int
    days_with_data: int
    coverage_percent: float
    avg_sample_count: Optional[float] = None


class ChartContextResponse(BaseModel):
    """Response for GET /analytics/chart-context."""
    metric_key: str
    display_name: str
    unit: str
    category: MetricCategory
    start_date: date
    end_date: date
    focus_date: Optional[date] = None
    time_series: TimeSeriesSummary
    baseline: BaselineSummary
    anomalies: AnomalySummary
    correlations: list[CorrelationItem]
    data_quality: DataQualityIndicators
