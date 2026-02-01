"""
Apple Health Analytics - DuckDB Builder

Creates curated analytics tables from Parquet data:
- daily_metrics: One row per (date, metric_key) with aggregated values
- baselines: 28-day rolling statistics for each metric
- anomalies: MAD-based anomaly detection
- correlations: Cross-metric correlations with lag analysis

Usage:
    python -m backend.healthdata.analytics.build_duckdb

Architecture:
- DuckDB queries Parquet directly via external views (no data copy)
- All analytics tables are reproducible and deterministic
- Raw Parquet remains immutable source of truth
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from backend.healthdata.config import DUCKDB_PATH, PARQUET_DIR, ensure_data_dirs

# =============================================================================
# METRIC TAXONOMY
# =============================================================================
# Each metric_key represents a meaningful daily signal.
#
# Heart Rate Metrics:
#   - heart_rate_mean: Average HR across all samples for the day
#   - heart_rate_min: Minimum HR of the day
#   - heart_rate_max: Maximum HR of the day
#   - resting_heart_rate: From HKQuantityTypeIdentifierRestingHeartRate
#
# HRV Metrics:
#   - hrv_sdnn: Median HRV SDNN per day
#
# Activity Metrics:
#   - steps: Daily sum of step count
#   - active_energy: Daily sum of active energy burned (kcal)
#   - basal_energy: Daily sum of basal energy burned (kcal)
#   - distance_walking_running: Daily sum (km)
#   - flights_climbed: Daily sum of floors climbed
#   - physical_effort_load: Sum of physical effort values
#
# Sleep Metrics:
#   - sleep_duration: Total asleep minutes per night
#
# Sparse/Reference Metrics (stored but excluded from baselines/anomalies):
#   - vo2max: Latest VO2 max value per day (sparse, ~monthly updates)
#
# EXCLUDED from daily_metrics (static or single-sample):
#   - body_mass: Too sparse, not daily signal
#   - height: Static measurement
#   - sleep_duration_goal: Goal setting, not health data
#
# Source Quality Ranking (used to pick best source when multiple exist):
#   1. Apple Watch (high)
#   2. WHOOP, Ultrahuman, Oura (medium)
#   3. iPhone, other apps (low)
# =============================================================================

# =============================================================================
# METRIC ELIGIBILITY RULES
# =============================================================================
# Only metrics in these allowlists will generate baselines and anomalies.
# This prevents noise from sparse or low-coverage metrics.
#
# IMPORTANT:
# - SPARSE_METRICS (vo2max, sleep_duration) are stored in daily_metrics
#   but MUST NOT appear in baselines or anomalies tables.
# - EXCLUDED_METRICS are not stored in daily_metrics at all.

# Sparse metrics: stored in daily_metrics but EXCLUDED from baselines AND anomalies
# These have insufficient daily coverage for meaningful baseline/anomaly detection
SPARSE_METRICS = [
    'vo2max',           # ~monthly updates, not daily
    'sleep_duration',   # Often has gaps, coverage too low for anomaly detection
]

# Metrics explicitly excluded from daily_metrics entirely (static/single-sample)
EXCLUDED_METRICS = [
    'body_mass',
    'height', 
    'sleep_duration_goal',
]

# Metrics eligible for baseline computation (require sufficient daily coverage)
# NOTE: This list must NOT include any SPARSE_METRICS
BASELINE_ELIGIBLE_METRICS = [
    'steps',
    'active_energy',
    'basal_energy',
    'distance_walking_running',
    'flights_climbed',
    'physical_effort_load',
    'heart_rate_mean',
    'heart_rate_min',
    'heart_rate_max',
    'resting_heart_rate',
    'hrv_sdnn',
    'exercise_time',
    'stand_hours',
    'walking_speed',
    'walking_step_length',
]

# Metrics eligible for anomaly detection
# NOTE: This list must NOT include any SPARSE_METRICS
# vo2max and sleep_duration are explicitly excluded
ANOMALY_ELIGIBLE_METRICS = [
    'steps',
    'active_energy',
    'basal_energy',
    'distance_walking_running',
    'flights_climbed',
    'physical_effort_load',
    'heart_rate_mean',
    'heart_rate_min',
    'heart_rate_max',
    'resting_heart_rate',
    'hrv_sdnn',
    'exercise_time',
    'stand_hours',
    'walking_speed',
    'walking_step_length',
]


def create_connection() -> duckdb.DuckDBPyConnection:
    """Create or open DuckDB connection."""
    ensure_data_dirs()
    DUCKDB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(DUCKDB_PATH))


def setup_views(con: duckdb.DuckDBPyConnection):
    """Create external views on Parquet files."""
    records_path = str(PARQUET_DIR / "records" / "**" / "*.parquet").replace("\\", "/")
    workouts_path = str(PARQUET_DIR / "workouts" / "**" / "*.parquet").replace("\\", "/")

    print("Creating Parquet views...")

    con.execute("DROP VIEW IF EXISTS records_parquet")
    con.execute("DROP VIEW IF EXISTS workouts_parquet")

    con.execute(f"""
        CREATE VIEW records_parquet AS
        SELECT * FROM read_parquet('{records_path}', hive_partitioning=true)
    """)

    con.execute(f"""
        CREATE VIEW workouts_parquet AS
        SELECT * FROM read_parquet('{workouts_path}', hive_partitioning=true)
    """)

    record_count = con.execute("SELECT COUNT(*) FROM records_parquet").fetchone()[0]
    workout_count = con.execute("SELECT COUNT(*) FROM workouts_parquet").fetchone()[0]
    print(f"  records_parquet: {record_count:,} rows")
    print(f"  workouts_parquet: {workout_count:,} rows")


def build_daily_metrics(con: duckdb.DuckDBPyConnection):
    """
    Build daily_metrics table with all metric aggregations.
    Each (date, metric_key) is unique - we aggregate across all sources per day.
    """
    print("\nBuilding daily_metrics table...")

    con.execute("DROP TABLE IF EXISTS daily_metrics")
    con.execute("""
        CREATE TABLE daily_metrics (
            date DATE,
            metric_key VARCHAR,
            value DOUBLE,
            unit VARCHAR,
            sample_count INTEGER,
            coverage_score DOUBLE,
            source_quality VARCHAR,
            computed_at TIMESTAMP,
            PRIMARY KEY (date, metric_key)
        )
    """)

    computed_at = datetime.now(timezone.utc).isoformat()

    # Helper to determine best source quality for a day
    source_quality_case = """
        CASE 
            WHEN SUM(CASE WHEN LOWER(source_name) LIKE '%watch%' THEN 1 ELSE 0 END) > 0 THEN 'high'
            WHEN SUM(CASE WHEN LOWER(source_name) LIKE '%whoop%' OR LOWER(source_name) LIKE '%oura%' OR LOWER(source_name) LIKE '%ultrahuman%' THEN 1 ELSE 0 END) > 0 THEN 'medium'
            ELSE 'low'
        END
    """

    # -------------------------------------------------------------------------
    # A. Heart Rate Metrics (HKQuantityTypeIdentifierHeartRate)
    # -------------------------------------------------------------------------
    print("  Processing heart rate metrics...")
    
    # heart_rate_mean
    con.execute(f"""
        INSERT INTO daily_metrics
        SELECT 
            CAST(start_ts AS DATE) as date,
            'heart_rate_mean' as metric_key,
            AVG(value) as value,
            'count/min' as unit,
            COUNT(*) as sample_count,
            LEAST(COUNT(*) / 1440.0, 1.0) as coverage_score,
            {source_quality_case} as source_quality,
            TIMESTAMP '{computed_at}' as computed_at
        FROM records_parquet
        WHERE type = 'HeartRate'
            AND value IS NOT NULL
            AND value > 30 AND value < 250
        GROUP BY CAST(start_ts AS DATE)
    """)

    # heart_rate_min
    con.execute(f"""
        INSERT INTO daily_metrics
        SELECT 
            CAST(start_ts AS DATE) as date,
            'heart_rate_min' as metric_key,
            MIN(value) as value,
            'count/min' as unit,
            COUNT(*) as sample_count,
            LEAST(COUNT(*) / 1440.0, 1.0) as coverage_score,
            {source_quality_case} as source_quality,
            TIMESTAMP '{computed_at}' as computed_at
        FROM records_parquet
        WHERE type = 'HeartRate'
            AND value IS NOT NULL
            AND value > 30 AND value < 250
        GROUP BY CAST(start_ts AS DATE)
    """)

    # heart_rate_max
    con.execute(f"""
        INSERT INTO daily_metrics
        SELECT 
            CAST(start_ts AS DATE) as date,
            'heart_rate_max' as metric_key,
            MAX(value) as value,
            'count/min' as unit,
            COUNT(*) as sample_count,
            LEAST(COUNT(*) / 1440.0, 1.0) as coverage_score,
            {source_quality_case} as source_quality,
            TIMESTAMP '{computed_at}' as computed_at
        FROM records_parquet
        WHERE type = 'HeartRate'
            AND value IS NOT NULL
            AND value > 30 AND value < 250
        GROUP BY CAST(start_ts AS DATE)
    """)

    # -------------------------------------------------------------------------
    # B. Resting Heart Rate (HKQuantityTypeIdentifierRestingHeartRate)
    # -------------------------------------------------------------------------
    print("  Processing resting heart rate...")
    con.execute(f"""
        INSERT INTO daily_metrics
        SELECT 
            CAST(start_ts AS DATE) as date,
            'resting_heart_rate' as metric_key,
            AVG(value) as value,
            'count/min' as unit,
            COUNT(*) as sample_count,
            CASE WHEN COUNT(*) >= 1 THEN 1.0 ELSE 0.0 END as coverage_score,
            'high' as source_quality,
            TIMESTAMP '{computed_at}' as computed_at
        FROM records_parquet
        WHERE type = 'RestingHeartRate'
            AND value IS NOT NULL
            AND value > 30 AND value < 150
        GROUP BY CAST(start_ts AS DATE)
    """)

    # -------------------------------------------------------------------------
    # C. HRV SDNN (HKQuantityTypeIdentifierHeartRateVariabilitySDNN)
    # -------------------------------------------------------------------------
    print("  Processing HRV SDNN...")
    con.execute(f"""
        INSERT INTO daily_metrics
        SELECT 
            CAST(start_ts AS DATE) as date,
            'hrv_sdnn' as metric_key,
            MEDIAN(value) as value,
            'ms' as unit,
            COUNT(*) as sample_count,
            LEAST(COUNT(*) / 10.0, 1.0) as coverage_score,
            'high' as source_quality,
            TIMESTAMP '{computed_at}' as computed_at
        FROM records_parquet
        WHERE type = 'HeartRateVariabilitySDNN'
            AND value IS NOT NULL
            AND value > 0 AND value < 300
        GROUP BY CAST(start_ts AS DATE)
    """)

    # -------------------------------------------------------------------------
    # D. Activity Metrics
    # -------------------------------------------------------------------------
    print("  Processing activity metrics...")

    # Steps - sum all sources per day
    con.execute(f"""
        INSERT INTO daily_metrics
        SELECT 
            CAST(start_ts AS DATE) as date,
            'steps' as metric_key,
            SUM(value) as value,
            'count' as unit,
            COUNT(*) as sample_count,
            LEAST(COUNT(*) / 100.0, 1.0) as coverage_score,
            {source_quality_case} as source_quality,
            TIMESTAMP '{computed_at}' as computed_at
        FROM records_parquet
        WHERE type = 'StepCount'
            AND value IS NOT NULL
            AND value >= 0
        GROUP BY CAST(start_ts AS DATE)
    """)

    # Active Energy
    con.execute(f"""
        INSERT INTO daily_metrics
        SELECT 
            CAST(start_ts AS DATE) as date,
            'active_energy' as metric_key,
            SUM(value) as value,
            'kcal' as unit,
            COUNT(*) as sample_count,
            LEAST(COUNT(*) / 100.0, 1.0) as coverage_score,
            {source_quality_case} as source_quality,
            TIMESTAMP '{computed_at}' as computed_at
        FROM records_parquet
        WHERE type = 'ActiveEnergyBurned'
            AND value IS NOT NULL
            AND value >= 0
        GROUP BY CAST(start_ts AS DATE)
    """)

    # Basal Energy
    con.execute(f"""
        INSERT INTO daily_metrics
        SELECT 
            CAST(start_ts AS DATE) as date,
            'basal_energy' as metric_key,
            SUM(value) as value,
            'kcal' as unit,
            COUNT(*) as sample_count,
            LEAST(COUNT(*) / 100.0, 1.0) as coverage_score,
            'high' as source_quality,
            TIMESTAMP '{computed_at}' as computed_at
        FROM records_parquet
        WHERE type = 'BasalEnergyBurned'
            AND value IS NOT NULL
            AND value >= 0
        GROUP BY CAST(start_ts AS DATE)
    """)

    # Distance Walking Running
    con.execute(f"""
        INSERT INTO daily_metrics
        SELECT 
            CAST(start_ts AS DATE) as date,
            'distance_walking_running' as metric_key,
            SUM(value) as value,
            'km' as unit,
            COUNT(*) as sample_count,
            LEAST(COUNT(*) / 50.0, 1.0) as coverage_score,
            {source_quality_case} as source_quality,
            TIMESTAMP '{computed_at}' as computed_at
        FROM records_parquet
        WHERE type = 'DistanceWalkingRunning'
            AND value IS NOT NULL
            AND value >= 0
        GROUP BY CAST(start_ts AS DATE)
    """)

    # Flights Climbed
    con.execute(f"""
        INSERT INTO daily_metrics
        SELECT 
            CAST(start_ts AS DATE) as date,
            'flights_climbed' as metric_key,
            SUM(value) as value,
            'count' as unit,
            COUNT(*) as sample_count,
            LEAST(COUNT(*) / 10.0, 1.0) as coverage_score,
            'medium' as source_quality,
            TIMESTAMP '{computed_at}' as computed_at
        FROM records_parquet
        WHERE type = 'FlightsClimbed'
            AND value IS NOT NULL
            AND value >= 0
        GROUP BY CAST(start_ts AS DATE)
    """)

    # -------------------------------------------------------------------------
    # E. Physical Effort
    # -------------------------------------------------------------------------
    print("  Processing physical effort...")
    con.execute(f"""
        INSERT INTO daily_metrics
        SELECT 
            CAST(start_ts AS DATE) as date,
            'physical_effort_load' as metric_key,
            SUM(value) as value,
            'arbitrary' as unit,
            COUNT(*) as sample_count,
            LEAST(COUNT(*) / 100.0, 1.0) as coverage_score,
            'high' as source_quality,
            TIMESTAMP '{computed_at}' as computed_at
        FROM records_parquet
        WHERE type = 'PhysicalEffort'
            AND value IS NOT NULL
        GROUP BY CAST(start_ts AS DATE)
    """)

    # -------------------------------------------------------------------------
    # F. Sleep Metrics
    # Sleep is assigned to the date the sleep STARTED
    # -------------------------------------------------------------------------
    print("  Processing sleep metrics...")
    
    sleep_count = con.execute("""
        SELECT COUNT(*) FROM records_parquet 
        WHERE type = 'cat_SleepAnalysis'
    """).fetchone()[0]
    
    if sleep_count > 0:
        con.execute(f"""
            INSERT INTO daily_metrics
            SELECT 
                CAST(start_ts AS DATE) as date,
                'sleep_duration' as metric_key,
                SUM(EXTRACT(EPOCH FROM (end_ts - start_ts)) / 60.0) as value,
                'minutes' as unit,
                COUNT(*) as sample_count,
                CASE WHEN COUNT(*) >= 1 THEN 1.0 ELSE 0.0 END as coverage_score,
                'high' as source_quality,
                TIMESTAMP '{computed_at}' as computed_at
            FROM records_parquet
            WHERE type = 'cat_SleepAnalysis'
                AND start_ts IS NOT NULL
                AND end_ts IS NOT NULL
            GROUP BY CAST(start_ts AS DATE)
        """)
        print(f"    Found {sleep_count:,} sleep records")
    else:
        print("    No sleep data found")

    # -------------------------------------------------------------------------
    # G. VO2 Max (sparse, latest value per day)
    # -------------------------------------------------------------------------
    print("  Processing VO2 Max...")
    con.execute(f"""
        INSERT INTO daily_metrics
        SELECT 
            CAST(start_ts AS DATE) as date,
            'vo2max' as metric_key,
            LAST(value ORDER BY start_ts) as value,
            'mL/kg/min' as unit,
            COUNT(*) as sample_count,
            1.0 as coverage_score,
            'high' as source_quality,
            TIMESTAMP '{computed_at}' as computed_at
        FROM records_parquet
        WHERE type = 'VO2Max'
            AND value IS NOT NULL
            AND value > 0
        GROUP BY CAST(start_ts AS DATE)
    """)

    # -------------------------------------------------------------------------
    # H. Body Mass - EXCLUDED (sparse, not daily signal)
    # -------------------------------------------------------------------------
    # body_mass is excluded from daily_metrics per eligibility rules
    # It's a static/sparse measurement, not a daily health signal
    print("  Skipping body mass (excluded - sparse metric)")

    # -------------------------------------------------------------------------
    # I. Apple Exercise Time
    # -------------------------------------------------------------------------
    print("  Processing exercise time...")
    con.execute(f"""
        INSERT INTO daily_metrics
        SELECT 
            CAST(start_ts AS DATE) as date,
            'exercise_time' as metric_key,
            SUM(value) as value,
            'min' as unit,
            COUNT(*) as sample_count,
            LEAST(COUNT(*) / 10.0, 1.0) as coverage_score,
            'high' as source_quality,
            TIMESTAMP '{computed_at}' as computed_at
        FROM records_parquet
        WHERE type = 'AppleExerciseTime'
            AND value IS NOT NULL
            AND value >= 0
        GROUP BY CAST(start_ts AS DATE)
    """)

    # -------------------------------------------------------------------------
    # J. Stand Hours
    # -------------------------------------------------------------------------
    print("  Processing stand hours...")
    con.execute(f"""
        INSERT INTO daily_metrics
        SELECT 
            CAST(start_ts AS DATE) as date,
            'stand_hours' as metric_key,
            COUNT(*) as value,
            'hours' as unit,
            COUNT(*) as sample_count,
            LEAST(COUNT(*) / 12.0, 1.0) as coverage_score,
            'high' as source_quality,
            TIMESTAMP '{computed_at}' as computed_at
        FROM records_parquet
        WHERE type = 'cat_AppleStandHour'
        GROUP BY CAST(start_ts AS DATE)
    """)

    # -------------------------------------------------------------------------
    # K. Walking metrics
    # -------------------------------------------------------------------------
    print("  Processing walking metrics...")
    
    # Walking speed (average)
    con.execute(f"""
        INSERT INTO daily_metrics
        SELECT 
            CAST(start_ts AS DATE) as date,
            'walking_speed' as metric_key,
            AVG(value) as value,
            'km/hr' as unit,
            COUNT(*) as sample_count,
            LEAST(COUNT(*) / 50.0, 1.0) as coverage_score,
            'high' as source_quality,
            TIMESTAMP '{computed_at}' as computed_at
        FROM records_parquet
        WHERE type = 'WalkingSpeed'
            AND value IS NOT NULL
            AND value > 0
        GROUP BY CAST(start_ts AS DATE)
    """)

    # Walking step length (average)
    con.execute(f"""
        INSERT INTO daily_metrics
        SELECT 
            CAST(start_ts AS DATE) as date,
            'walking_step_length' as metric_key,
            AVG(value) as value,
            'cm' as unit,
            COUNT(*) as sample_count,
            LEAST(COUNT(*) / 50.0, 1.0) as coverage_score,
            'high' as source_quality,
            TIMESTAMP '{computed_at}' as computed_at
        FROM records_parquet
        WHERE type = 'WalkingStepLength'
            AND value IS NOT NULL
            AND value > 0
        GROUP BY CAST(start_ts AS DATE)
    """)

    # Summary
    total_rows = con.execute("SELECT COUNT(*) FROM daily_metrics").fetchone()[0]
    unique_metrics = con.execute("SELECT COUNT(DISTINCT metric_key) FROM daily_metrics").fetchone()[0]
    date_range = con.execute("SELECT MIN(date), MAX(date) FROM daily_metrics").fetchone()

    print(f"\n  daily_metrics built:")
    print(f"    Total rows: {total_rows:,}")
    print(f"    Unique metrics: {unique_metrics}")
    print(f"    Date range: {date_range[0]} to {date_range[1]}")


def build_baselines(con: duckdb.DuckDBPyConnection):
    """
    Build baselines table with 28-day rolling statistics.
    Window is 28 days BEFORE the current date (no leakage).
    Requires minimum 10 data points.
    Only includes metrics in BASELINE_ELIGIBLE_METRICS allowlist.
    """
    print("\nBuilding baselines table...")
    
    # Build SQL allowlist string
    eligible_metrics_sql = ", ".join([f"'{m}'" for m in BASELINE_ELIGIBLE_METRICS])
    print(f"  Eligible metrics: {len(BASELINE_ELIGIBLE_METRICS)}")

    con.execute("DROP TABLE IF EXISTS baselines")
    con.execute("""
        CREATE TABLE baselines (
            date DATE,
            metric_key VARCHAR,
            baseline_28d_median DOUBLE,
            baseline_28d_p25 DOUBLE,
            baseline_28d_p75 DOUBLE,
            baseline_28d_mad DOUBLE,
            data_points INTEGER,
            PRIMARY KEY (date, metric_key)
        )
    """)

    con.execute(f"""
        INSERT INTO baselines
        WITH daily_values AS (
            SELECT 
                date,
                metric_key,
                value
            FROM daily_metrics
            WHERE value IS NOT NULL
                AND metric_key IN ({eligible_metrics_sql})
        ),
        rolling_stats AS (
            SELECT 
                d1.date,
                d1.metric_key,
                MEDIAN(d2.value) as baseline_28d_median,
                PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY d2.value) as baseline_28d_p25,
                PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY d2.value) as baseline_28d_p75,
                COUNT(d2.value) as data_points
            FROM daily_values d1
            LEFT JOIN daily_values d2 
                ON d1.metric_key = d2.metric_key
                AND d2.date >= d1.date - INTERVAL 28 DAY
                AND d2.date < d1.date
            GROUP BY d1.date, d1.metric_key
            HAVING COUNT(d2.value) >= 10
        )
        SELECT 
            rs.date,
            rs.metric_key,
            rs.baseline_28d_median,
            rs.baseline_28d_p25,
            rs.baseline_28d_p75,
            NULL as baseline_28d_mad,
            rs.data_points
        FROM rolling_stats rs
    """)

    # Update MAD (Median Absolute Deviation)
    con.execute("""
        UPDATE baselines b
        SET baseline_28d_mad = (
            SELECT MEDIAN(ABS(dm.value - b.baseline_28d_median))
            FROM daily_metrics dm
            WHERE dm.metric_key = b.metric_key
                AND dm.date >= b.date - INTERVAL 28 DAY
                AND dm.date < b.date
                AND dm.value IS NOT NULL
        )
        WHERE baseline_28d_median IS NOT NULL
    """)

    total_rows = con.execute("SELECT COUNT(*) FROM baselines").fetchone()[0]
    metrics_with_baselines = con.execute("SELECT COUNT(DISTINCT metric_key) FROM baselines").fetchone()[0]

    print(f"  baselines built:")
    print(f"    Total rows: {total_rows:,}")
    print(f"    Metrics with baselines: {metrics_with_baselines}")


def build_anomalies(con: duckdb.DuckDBPyConnection):
    """
    Build anomalies table using MAD-based z-scores.
    z = (value - median) / (1.4826 * MAD)
    Thresholds: |z| < 2.5 → none, 2.5-3.5 → mild, ≥3.5 → strong
    Only includes metrics in ANOMALY_ELIGIBLE_METRICS allowlist.
    """
    print("\nBuilding anomalies table...")
    
    # Build SQL allowlist string
    eligible_metrics_sql = ", ".join([f"'{m}'" for m in ANOMALY_ELIGIBLE_METRICS])
    print(f"  Eligible metrics: {len(ANOMALY_ELIGIBLE_METRICS)}")

    con.execute("DROP TABLE IF EXISTS anomalies")
    con.execute("""
        CREATE TABLE anomalies (
            date DATE,
            metric_key VARCHAR,
            value DOUBLE,
            baseline_median DOUBLE,
            z_mad DOUBLE,
            anomaly_level VARCHAR,
            reason VARCHAR,
            PRIMARY KEY (date, metric_key)
        )
    """)

    con.execute(f"""
        INSERT INTO anomalies
        SELECT 
            dm.date,
            dm.metric_key,
            dm.value,
            b.baseline_28d_median as baseline_median,
            CASE 
                WHEN b.baseline_28d_mad > 0 
                THEN (dm.value - b.baseline_28d_median) / (1.4826 * b.baseline_28d_mad)
                ELSE 0
            END as z_mad,
            CASE 
                WHEN b.baseline_28d_mad > 0 AND ABS((dm.value - b.baseline_28d_median) / (1.4826 * b.baseline_28d_mad)) >= 3.5 THEN 'strong'
                WHEN b.baseline_28d_mad > 0 AND ABS((dm.value - b.baseline_28d_median) / (1.4826 * b.baseline_28d_mad)) >= 2.5 THEN 'mild'
                ELSE 'none'
            END as anomaly_level,
            CASE 
                WHEN b.baseline_28d_mad > 0 AND (dm.value - b.baseline_28d_median) / (1.4826 * b.baseline_28d_mad) >= 3.5 
                    THEN dm.metric_key || ' unusually high (' || ROUND(dm.value, 1) || ' vs baseline ' || ROUND(b.baseline_28d_median, 1) || ')'
                WHEN b.baseline_28d_mad > 0 AND (dm.value - b.baseline_28d_median) / (1.4826 * b.baseline_28d_mad) <= -3.5 
                    THEN dm.metric_key || ' unusually low (' || ROUND(dm.value, 1) || ' vs baseline ' || ROUND(b.baseline_28d_median, 1) || ')'
                WHEN b.baseline_28d_mad > 0 AND (dm.value - b.baseline_28d_median) / (1.4826 * b.baseline_28d_mad) >= 2.5 
                    THEN dm.metric_key || ' elevated (' || ROUND(dm.value, 1) || ' vs baseline ' || ROUND(b.baseline_28d_median, 1) || ')'
                WHEN b.baseline_28d_mad > 0 AND (dm.value - b.baseline_28d_median) / (1.4826 * b.baseline_28d_mad) <= -2.5 
                    THEN dm.metric_key || ' reduced (' || ROUND(dm.value, 1) || ' vs baseline ' || ROUND(b.baseline_28d_median, 1) || ')'
                ELSE 'within normal range'
            END as reason
        FROM daily_metrics dm
        JOIN baselines b ON dm.date = b.date AND dm.metric_key = b.metric_key
        WHERE dm.metric_key IN ({eligible_metrics_sql})
            AND dm.value IS NOT NULL
            AND b.baseline_28d_median IS NOT NULL
            AND b.baseline_28d_mad IS NOT NULL
            AND b.baseline_28d_mad > 0
    """)

    total_rows = con.execute("SELECT COUNT(*) FROM anomalies").fetchone()[0]
    mild_count = con.execute("SELECT COUNT(*) FROM anomalies WHERE anomaly_level = 'mild'").fetchone()[0]
    strong_count = con.execute("SELECT COUNT(*) FROM anomalies WHERE anomaly_level = 'strong'").fetchone()[0]

    print(f"  anomalies built:")
    print(f"    Total rows: {total_rows:,}")
    print(f"    Mild anomalies: {mild_count:,}")
    print(f"    Strong anomalies: {strong_count:,}")


def build_correlations(con: duckdb.DuckDBPyConnection):
    """
    Build correlations table for cross-metric analysis.
    Test lags from -3 to +3 days.
    Require minimum 30 overlapping data points.
    Store only correlations with |corr| >= 0.2.
    """
    print("\nBuilding correlations table...")

    con.execute("DROP TABLE IF EXISTS correlations")
    con.execute("""
        CREATE TABLE correlations (
            metric_a VARCHAR,
            metric_b VARCHAR,
            lag_days INTEGER,
            corr DOUBLE,
            n INTEGER,
            window_days INTEGER,
            PRIMARY KEY (metric_a, metric_b, lag_days)
        )
    """)

    metric_pairs = [
        ('sleep_duration', 'hrv_sdnn'),
        ('sleep_duration', 'resting_heart_rate'),
        ('physical_effort_load', 'resting_heart_rate'),
        ('physical_effort_load', 'hrv_sdnn'),
        ('steps', 'sleep_duration'),
        ('steps', 'active_energy'),
        ('active_energy', 'resting_heart_rate'),
        ('exercise_time', 'hrv_sdnn'),
        ('steps', 'resting_heart_rate'),
        ('active_energy', 'hrv_sdnn'),
    ]

    inserted = 0
    for metric_a, metric_b in metric_pairs:
        for lag in range(-3, 4):
            try:
                result = con.execute(f"""
                    SELECT 
                        CORR(a.value, b.value) as corr,
                        COUNT(*) as n
                    FROM daily_metrics a
                    JOIN daily_metrics b 
                        ON a.date = b.date + INTERVAL {lag} DAY
                        AND a.metric_key = '{metric_a}'
                        AND b.metric_key = '{metric_b}'
                    WHERE a.value IS NOT NULL 
                        AND b.value IS NOT NULL
                """).fetchone()
                
                if result and result[1] >= 30 and result[0] is not None and abs(result[0]) >= 0.2:
                    con.execute(f"""
                        INSERT INTO correlations VALUES 
                        ('{metric_a}', '{metric_b}', {lag}, {result[0]}, {result[1]}, 90)
                    """)
                    inserted += 1
            except Exception:
                pass

    print(f"  correlations built:")
    print(f"    Total rows: {inserted}")


def validate_and_summarize(con: duckdb.DuckDBPyConnection):
    """Run validation checks and print summary."""
    print("\n" + "=" * 60)
    print("Validation and Summary")
    print("=" * 60)

    # -------------------------------------------------------------------------
    # Verify excluded metrics are NOT present
    # -------------------------------------------------------------------------
    print("\nExcluded metrics check:")
    excluded_check = EXCLUDED_METRICS + SPARSE_METRICS
    for metric in excluded_check:
        in_baselines = con.execute(f"SELECT COUNT(*) FROM baselines WHERE metric_key = '{metric}'").fetchone()[0]
        in_anomalies = con.execute(f"SELECT COUNT(*) FROM anomalies WHERE metric_key = '{metric}'").fetchone()[0]
        in_daily = con.execute(f"SELECT COUNT(*) FROM daily_metrics WHERE metric_key = '{metric}'").fetchone()[0]
        
        if metric in EXCLUDED_METRICS:
            # Should not be in daily_metrics at all
            status = "✓ NOT in daily_metrics" if in_daily == 0 else f"✗ FOUND {in_daily} rows in daily_metrics"
            print(f"  {metric}: {status}")
        else:
            # Sparse metrics: allowed in daily_metrics but not in baselines/anomalies
            baseline_status = "✓" if in_baselines == 0 else f"✗ {in_baselines}"
            anomaly_status = "✓" if in_anomalies == 0 else f"✗ {in_anomalies}"
            print(f"  {metric}: daily={in_daily}, baselines={baseline_status}, anomalies={anomaly_status}")

    print("\nTable row counts:")
    for table in ['daily_metrics', 'baselines', 'anomalies', 'correlations']:
        count = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table}: {count:,}")

    print("\nBaselines row count per metric:")
    baselines_by_metric = con.execute("""
        SELECT metric_key, COUNT(*) as rows
        FROM baselines
        GROUP BY metric_key
        ORDER BY rows DESC
    """).fetchdf()
    for _, row in baselines_by_metric.iterrows():
        print(f"  {row['metric_key']}: {row['rows']:,}")

    print("\nAnomalies row count per metric:")
    anomalies_by_metric = con.execute("""
        SELECT metric_key, COUNT(*) as rows
        FROM anomalies
        GROUP BY metric_key
        ORDER BY rows DESC
    """).fetchdf()
    for _, row in anomalies_by_metric.iterrows():
        print(f"  {row['metric_key']}: {row['rows']:,}")

    print("\nMetrics in daily_metrics:")
    metrics = con.execute("""
        SELECT metric_key, COUNT(*) as days, MIN(date) as first_date, MAX(date) as last_date
        FROM daily_metrics
        GROUP BY metric_key
        ORDER BY days DESC
    """).fetchdf()
    for _, row in metrics.iterrows():
        print(f"  {row['metric_key']}: {row['days']:,} days ({row['first_date']} to {row['last_date']})")

    print("\nAnomaly distribution by metric (mild/strong):")
    anomaly_dist = con.execute("""
        SELECT metric_key, anomaly_level, COUNT(*) as cnt
        FROM anomalies
        WHERE anomaly_level != 'none'
        GROUP BY metric_key, anomaly_level
        ORDER BY metric_key, anomaly_level
    """).fetchdf()
    if len(anomaly_dist) > 0:
        for _, row in anomaly_dist.iterrows():
            print(f"  {row['metric_key']} - {row['anomaly_level']}: {row['cnt']}")
    else:
        print("  No anomalies detected")

    print("\nTop correlations:")
    top_corr = con.execute("""
        SELECT metric_a, metric_b, lag_days, ROUND(corr, 3) as corr, n
        FROM correlations
        ORDER BY ABS(corr) DESC
        LIMIT 10
    """).fetchdf()
    if len(top_corr) > 0:
        for _, row in top_corr.iterrows():
            print(f"  {row['metric_a']} ↔ {row['metric_b']} (lag={row['lag_days']}): r={row['corr']} (n={row['n']})")
    else:
        print("  No significant correlations found")

    print("\nSample daily_metrics rows (steps):")
    sample = con.execute("""
        SELECT date, metric_key, ROUND(value, 1) as value, unit, sample_count
        FROM daily_metrics
        WHERE metric_key = 'steps'
        ORDER BY date DESC
        LIMIT 5
    """).fetchdf()
    if len(sample) > 0:
        print(sample.to_string(index=False))
    else:
        print("  No steps data")

    print("\nSample daily_metrics rows (heart_rate_mean):")
    sample_hr = con.execute("""
        SELECT date, metric_key, ROUND(value, 1) as value, unit, sample_count
        FROM daily_metrics
        WHERE metric_key = 'heart_rate_mean'
        ORDER BY date DESC
        LIMIT 5
    """).fetchdf()
    if len(sample_hr) > 0:
        print(sample_hr.to_string(index=False))
    else:
        print("  No heart rate data")


def main():
    """Main entry point for building DuckDB analytics."""
    print("=" * 60)
    print("Apple Health Analytics - DuckDB Builder")
    print("=" * 60)
    print(f"\nDuckDB path: {DUCKDB_PATH}")
    print(f"Parquet path: {PARQUET_DIR}")

    con = create_connection()

    try:
        setup_views(con)
        build_daily_metrics(con)
        build_baselines(con)
        build_anomalies(con)
        build_correlations(con)
        validate_and_summarize(con)

        print("\n" + "=" * 60)
        print("Phase 3 Complete!")
        print("=" * 60)
        print(f"\nDuckDB file: {DUCKDB_PATH}")
        print("\nTables created:")
        print("  - daily_metrics (curated daily aggregates)")
        print("  - baselines (28-day rolling statistics)")
        print("  - anomalies (MAD-based anomaly detection)")
        print("  - correlations (cross-metric correlations)")

    finally:
        con.close()


if __name__ == "__main__":
    main()
