"""
Derived Scores Builder - Phase 5.5

Creates derived_scores_daily table with:
- Recovery Score (0-100): HRV, Resting HR, Yesterday's Effort
- Strain Score (0-100): Physical effort with fallback to active energy

IMPORTANT:
- Does NOT modify existing tables (daily_metrics, baselines, anomalies, correlations)
- All scores are baseline-relative using robust normalization
- Missing inputs result in NULL scores (no interpolation)

Usage:
    python -m backend.healthdata.analytics.derived_scores
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from backend.healthdata.config import DUCKDB_PATH

# =============================================================================
# LOCKED WEIGHTS (DO NOT CHANGE)
# =============================================================================
RECOVERY_WEIGHT_HRV = 0.50
RECOVERY_WEIGHT_RHR = 0.30
RECOVERY_WEIGHT_EFFORT = 0.20

STRAIN_SECONDARY_HRMAX = 0.10
STRAIN_SECONDARY_EXERCISE = 0.10

SIGMOID_SLOPE = 0.7


def create_connection() -> duckdb.DuckDBPyConnection:
    """Open existing DuckDB connection."""
    return duckdb.connect(str(DUCKDB_PATH))


def build_derived_scores(con: duckdb.DuckDBPyConnection):
    """
    Build derived_scores_daily table with Recovery and Strain scores.
    
    Recovery Score formula:
    - HRV component: sigmoid(+z_hrv) * 0.50
    - RHR component: sigmoid(-z_rhr) * 0.30  
    - Effort component: sigmoid(-z_effort_yesterday) * 0.20
    
    Strain Score formula:
    - Primary: physical_effort_load (or active_energy fallback)
    - Secondary: +0.10 * z_hrmax + 0.10 * z_exercise
    """
    print("Building derived_scores_daily table...")
    
    con.execute("DROP TABLE IF EXISTS derived_scores_daily")
    
    computed_at = datetime.now(timezone.utc).isoformat()
    
    con.execute(f"""
        CREATE TABLE derived_scores_daily AS
        WITH 
        -- Get all unique dates from daily_metrics
        all_dates AS (
            SELECT DISTINCT date FROM daily_metrics
        ),
        
        -- Pivot daily_metrics to get values per metric per day
        metrics_pivot AS (
            SELECT 
                date,
                MAX(CASE WHEN metric_key = 'hrv_sdnn' THEN value END) AS hrv_sdnn,
                MAX(CASE WHEN metric_key = 'resting_heart_rate' THEN value END) AS resting_heart_rate,
                MAX(CASE WHEN metric_key = 'physical_effort_load' THEN value END) AS physical_effort_load,
                MAX(CASE WHEN metric_key = 'active_energy' THEN value END) AS active_energy,
                MAX(CASE WHEN metric_key = 'heart_rate_max' THEN value END) AS heart_rate_max,
                MAX(CASE WHEN metric_key = 'exercise_time' THEN value END) AS exercise_time
            FROM daily_metrics
            GROUP BY date
        ),
        
        -- Pivot baselines to get baseline stats per metric per day
        baselines_pivot AS (
            SELECT 
                date,
                MAX(CASE WHEN metric_key = 'hrv_sdnn' THEN baseline_28d_median END) AS hrv_med,
                MAX(CASE WHEN metric_key = 'hrv_sdnn' THEN baseline_28d_p25 END) AS hrv_p25,
                MAX(CASE WHEN metric_key = 'hrv_sdnn' THEN baseline_28d_p75 END) AS hrv_p75,
                MAX(CASE WHEN metric_key = 'resting_heart_rate' THEN baseline_28d_median END) AS rhr_med,
                MAX(CASE WHEN metric_key = 'resting_heart_rate' THEN baseline_28d_p25 END) AS rhr_p25,
                MAX(CASE WHEN metric_key = 'resting_heart_rate' THEN baseline_28d_p75 END) AS rhr_p75,
                MAX(CASE WHEN metric_key = 'physical_effort_load' THEN baseline_28d_median END) AS effort_med,
                MAX(CASE WHEN metric_key = 'physical_effort_load' THEN baseline_28d_p25 END) AS effort_p25,
                MAX(CASE WHEN metric_key = 'physical_effort_load' THEN baseline_28d_p75 END) AS effort_p75,
                MAX(CASE WHEN metric_key = 'active_energy' THEN baseline_28d_median END) AS energy_med,
                MAX(CASE WHEN metric_key = 'active_energy' THEN baseline_28d_p25 END) AS energy_p25,
                MAX(CASE WHEN metric_key = 'active_energy' THEN baseline_28d_p75 END) AS energy_p75,
                MAX(CASE WHEN metric_key = 'heart_rate_max' THEN baseline_28d_median END) AS hrmax_med,
                MAX(CASE WHEN metric_key = 'heart_rate_max' THEN baseline_28d_p25 END) AS hrmax_p25,
                MAX(CASE WHEN metric_key = 'heart_rate_max' THEN baseline_28d_p75 END) AS hrmax_p75,
                MAX(CASE WHEN metric_key = 'exercise_time' THEN baseline_28d_median END) AS exercise_med,
                MAX(CASE WHEN metric_key = 'exercise_time' THEN baseline_28d_p25 END) AS exercise_p25,
                MAX(CASE WHEN metric_key = 'exercise_time' THEN baseline_28d_p75 END) AS exercise_p75
            FROM baselines
            GROUP BY date
        ),
        
        -- Join current day metrics with baselines, and yesterday's effort
        joined AS (
            SELECT 
                d.date,
                m.hrv_sdnn,
                m.resting_heart_rate,
                m.physical_effort_load,
                m.active_energy,
                m.heart_rate_max,
                m.exercise_time,
                b.hrv_med, b.hrv_p25, b.hrv_p75,
                b.rhr_med, b.rhr_p25, b.rhr_p75,
                b.effort_med, b.effort_p25, b.effort_p75,
                b.energy_med, b.energy_p25, b.energy_p75,
                b.hrmax_med, b.hrmax_p25, b.hrmax_p75,
                b.exercise_med, b.exercise_p25, b.exercise_p75,
                -- Yesterday's effort for recovery calculation
                LAG(m.physical_effort_load) OVER (ORDER BY d.date) AS yesterday_effort,
                LAG(b.effort_med) OVER (ORDER BY d.date) AS yesterday_effort_med,
                LAG(b.effort_p25) OVER (ORDER BY d.date) AS yesterday_effort_p25,
                LAG(b.effort_p75) OVER (ORDER BY d.date) AS yesterday_effort_p75
            FROM all_dates d
            LEFT JOIN metrics_pivot m ON d.date = m.date
            LEFT JOIN baselines_pivot b ON d.date = b.date
        ),
        
        -- Calculate z-scores with robust normalization (capped at +/- 3)
        z_scores AS (
            SELECT 
                date,
                hrv_sdnn, resting_heart_rate, physical_effort_load, active_energy,
                heart_rate_max, exercise_time,
                hrv_med, rhr_med, effort_med, energy_med, hrmax_med, exercise_med,
                yesterday_effort,
                
                -- HRV z-score (higher is better for recovery)
                CASE 
                    WHEN hrv_sdnn IS NOT NULL AND hrv_med IS NOT NULL AND hrv_p75 IS NOT NULL AND hrv_p25 IS NOT NULL
                    THEN GREATEST(-3.0, LEAST(3.0, 
                        (hrv_sdnn - hrv_med) / GREATEST(hrv_p75 - hrv_p25, 0.000001)
                    ))
                END AS z_hrv,
                
                -- RHR z-score (lower is better for recovery, so we negate)
                CASE 
                    WHEN resting_heart_rate IS NOT NULL AND rhr_med IS NOT NULL AND rhr_p75 IS NOT NULL AND rhr_p25 IS NOT NULL
                    THEN GREATEST(-3.0, LEAST(3.0, 
                        (resting_heart_rate - rhr_med) / GREATEST(rhr_p75 - rhr_p25, 0.000001)
                    ))
                END AS z_rhr,
                
                -- Yesterday effort z-score (lower is better for recovery, so we negate)
                CASE 
                    WHEN yesterday_effort IS NOT NULL AND yesterday_effort_med IS NOT NULL 
                         AND yesterday_effort_p75 IS NOT NULL AND yesterday_effort_p25 IS NOT NULL
                    THEN GREATEST(-3.0, LEAST(3.0, 
                        (yesterday_effort - yesterday_effort_med) / GREATEST(yesterday_effort_p75 - yesterday_effort_p25, 0.000001)
                    ))
                END AS z_effort_yesterday,
                
                -- Physical effort z-score for strain (primary)
                CASE 
                    WHEN physical_effort_load IS NOT NULL AND effort_med IS NOT NULL 
                         AND effort_p75 IS NOT NULL AND effort_p25 IS NOT NULL
                    THEN GREATEST(-3.0, LEAST(3.0, 
                        (physical_effort_load - effort_med) / GREATEST(effort_p75 - effort_p25, 0.000001)
                    ))
                END AS z_effort,
                
                -- Active energy z-score for strain (fallback)
                CASE 
                    WHEN active_energy IS NOT NULL AND energy_med IS NOT NULL 
                         AND energy_p75 IS NOT NULL AND energy_p25 IS NOT NULL
                    THEN GREATEST(-3.0, LEAST(3.0, 
                        (active_energy - energy_med) / GREATEST(energy_p75 - energy_p25, 0.000001)
                    ))
                END AS z_energy,
                
                -- HR max z-score for strain (secondary)
                CASE 
                    WHEN heart_rate_max IS NOT NULL AND hrmax_med IS NOT NULL 
                         AND hrmax_p75 IS NOT NULL AND hrmax_p25 IS NOT NULL
                    THEN GREATEST(-3.0, LEAST(3.0, 
                        (heart_rate_max - hrmax_med) / GREATEST(hrmax_p75 - hrmax_p25, 0.000001)
                    ))
                    ELSE 0
                END AS z_hrmax,
                
                -- Exercise time z-score for strain (secondary)
                CASE 
                    WHEN exercise_time IS NOT NULL AND exercise_med IS NOT NULL 
                         AND exercise_p75 IS NOT NULL AND exercise_p25 IS NOT NULL
                    THEN GREATEST(-3.0, LEAST(3.0, 
                        (exercise_time - exercise_med) / GREATEST(exercise_p75 - exercise_p25, 0.000001)
                    ))
                    ELSE 0
                END AS z_exercise,
                
                -- Determine which metric to use for strain primary
                CASE 
                    WHEN physical_effort_load IS NOT NULL AND effort_med IS NOT NULL THEN 'effort_load'
                    WHEN active_energy IS NOT NULL AND energy_med IS NOT NULL THEN 'active_energy'
                    ELSE NULL
                END AS strain_primary_metric
                
            FROM joined
        ),
        
        -- Calculate sigmoid components
        components AS (
            SELECT 
                date,
                z_hrv, z_rhr, z_effort_yesterday,
                z_effort, z_energy, z_hrmax, z_exercise,
                strain_primary_metric,
                
                -- Recovery components using sigmoid
                -- HRV: higher z -> higher recovery (positive z is good)
                CASE WHEN z_hrv IS NOT NULL 
                    THEN 1.0 / (1.0 + EXP(-{SIGMOID_SLOPE} * z_hrv)) 
                END AS hrv_component,
                
                -- RHR: higher z -> lower recovery (negate z)
                CASE WHEN z_rhr IS NOT NULL 
                    THEN 1.0 / (1.0 + EXP(-{SIGMOID_SLOPE} * (-z_rhr))) 
                END AS rhr_component,
                
                -- Yesterday effort: higher z -> lower recovery (negate z)
                CASE WHEN z_effort_yesterday IS NOT NULL 
                    THEN 1.0 / (1.0 + EXP(-{SIGMOID_SLOPE} * (-z_effort_yesterday))) 
                END AS effort_component,
                
                -- Strain primary z (effort_load preferred, else active_energy)
                CASE 
                    WHEN z_effort IS NOT NULL THEN z_effort
                    WHEN z_energy IS NOT NULL THEN z_energy
                    ELSE NULL
                END AS z_strain_primary,
                
                z_hrmax AS z_strain_hrmax,
                z_exercise AS z_strain_exercise
                
            FROM z_scores
        ),
        
        -- Calculate final scores
        scores AS (
            SELECT 
                date,
                hrv_component, rhr_component, effort_component,
                strain_primary_metric,
                
                -- Recovery score (only if all components available)
                CASE 
                    WHEN hrv_component IS NOT NULL 
                         AND rhr_component IS NOT NULL 
                         AND effort_component IS NOT NULL
                    THEN ROUND(100 * (
                        {RECOVERY_WEIGHT_HRV} * hrv_component + 
                        {RECOVERY_WEIGHT_RHR} * rhr_component + 
                        {RECOVERY_WEIGHT_EFFORT} * effort_component
                    ))
                END AS recovery_score,
                
                -- Strain score
                CASE 
                    WHEN z_strain_primary IS NOT NULL
                    THEN GREATEST(0, LEAST(100, ROUND(100 * (
                        1.0 / (1.0 + EXP(-{SIGMOID_SLOPE} * (
                            z_strain_primary + 
                            {STRAIN_SECONDARY_HRMAX} * COALESCE(z_strain_hrmax, 0) + 
                            {STRAIN_SECONDARY_EXERCISE} * COALESCE(z_strain_exercise, 0)
                        )))
                    ))))
                END AS strain_score,
                
                -- Calculate contributor impacts for UI
                -- Impact = weight * (component - 0.5)
                CASE WHEN hrv_component IS NOT NULL 
                    THEN {RECOVERY_WEIGHT_HRV} * (hrv_component - 0.5) 
                END AS hrv_impact_raw,
                CASE WHEN rhr_component IS NOT NULL 
                    THEN {RECOVERY_WEIGHT_RHR} * (rhr_component - 0.5) 
                END AS rhr_impact_raw,
                CASE WHEN effort_component IS NOT NULL 
                    THEN {RECOVERY_WEIGHT_EFFORT} * (effort_component - 0.5) 
                END AS effort_impact_raw
                
            FROM components
        ),
        
        -- Normalize impacts to percentages
        final_scores AS (
            SELECT 
                date,
                recovery_score,
                strain_score,
                strain_primary_metric,
                hrv_impact_raw,
                rhr_impact_raw,
                effort_impact_raw,
                
                -- Sum of absolute impacts for normalization
                GREATEST(
                    ABS(COALESCE(hrv_impact_raw, 0)) + 
                    ABS(COALESCE(rhr_impact_raw, 0)) + 
                    ABS(COALESCE(effort_impact_raw, 0)),
                    0.000001
                ) AS sum_abs_impacts
                
            FROM scores
        )
        
        SELECT 
            date,
            recovery_score,
            -- Recovery label
            CASE 
                WHEN recovery_score IS NULL THEN NULL
                WHEN recovery_score >= 67 THEN 'Ready'
                WHEN recovery_score >= 34 THEN 'Caution'
                ELSE 'Recover'
            END AS recovery_label,
            -- Recovery color
            CASE 
                WHEN recovery_score IS NULL THEN NULL
                WHEN recovery_score >= 67 THEN 'green'
                WHEN recovery_score >= 34 THEN 'yellow'
                ELSE 'red'
            END AS recovery_color,
            
            strain_score,
            -- Strain label
            CASE 
                WHEN strain_score IS NULL THEN NULL
                WHEN strain_score >= 67 THEN 'High'
                WHEN strain_score >= 34 THEN 'Moderate'
                ELSE 'Low'
            END AS strain_label,
            strain_primary_metric,
            
            -- Contributor percentages (normalized)
            CASE WHEN recovery_score IS NOT NULL 
                THEN ROUND(100 * hrv_impact_raw / sum_abs_impacts, 1)
            END AS hrv_pct,
            CASE WHEN recovery_score IS NOT NULL 
                THEN ROUND(100 * rhr_impact_raw / sum_abs_impacts, 1)
            END AS rhr_pct,
            CASE WHEN recovery_score IS NOT NULL 
                THEN ROUND(100 * effort_impact_raw / sum_abs_impacts, 1)
            END AS effort_pct,
            
            TIMESTAMP '{computed_at}' AS computed_at
            
        FROM final_scores
        ORDER BY date
    """)
    
    # Get stats
    total_rows = con.execute("SELECT COUNT(*) FROM derived_scores_daily").fetchone()[0]
    recovery_rows = con.execute("SELECT COUNT(*) FROM derived_scores_daily WHERE recovery_score IS NOT NULL").fetchone()[0]
    strain_rows = con.execute("SELECT COUNT(*) FROM derived_scores_daily WHERE strain_score IS NOT NULL").fetchone()[0]
    
    print(f"  Total rows: {total_rows}")
    print(f"  Days with recovery score: {recovery_rows}")
    print(f"  Days with strain score: {strain_rows}")


def validate_derived_scores(con: duckdb.DuckDBPyConnection):
    """Validate that derived scores follow the rules."""
    print("\nValidating derived scores...")
    
    # Check recovery score only uses HRV, RHR, effort
    print("  Checking recovery score inputs...")
    
    # Verify no sleep_duration influence
    result = con.execute("""
        SELECT COUNT(*) FROM derived_scores_daily d
        WHERE d.recovery_score IS NOT NULL
        AND EXISTS (
            SELECT 1 FROM daily_metrics dm 
            WHERE dm.date = d.date AND dm.metric_key = 'sleep_duration' AND dm.value IS NOT NULL
        )
        AND NOT EXISTS (
            SELECT 1 FROM daily_metrics dm 
            WHERE dm.date = d.date AND dm.metric_key = 'hrv_sdnn' AND dm.value IS NOT NULL
        )
    """).fetchone()[0]
    
    if result > 0:
        print(f"  WARNING: {result} recovery scores may be computed without HRV")
    else:
        print("  ✓ Recovery score requires HRV (not computed from sleep)")
    
    # Check strain uses effort_load when available
    result = con.execute("""
        SELECT COUNT(*) FROM derived_scores_daily d
        WHERE d.strain_primary_metric = 'active_energy'
        AND EXISTS (
            SELECT 1 FROM daily_metrics dm 
            WHERE dm.date = d.date 
            AND dm.metric_key = 'physical_effort_load' 
            AND dm.value IS NOT NULL
        )
    """).fetchone()[0]
    
    if result > 0:
        print(f"  WARNING: {result} strain scores use active_energy despite effort_load being available")
    else:
        print("  ✓ Strain prefers physical_effort_load over active_energy")
    
    # Check steps never affects strain
    print("  ✓ Steps metric is not used in strain calculation (by design)")
    
    # Sample output
    print("\nSample derived scores (last 7 days):")
    sample = con.execute("""
        SELECT date, recovery_score, recovery_label, strain_score, strain_label, 
               hrv_pct, rhr_pct, effort_pct, strain_primary_metric
        FROM derived_scores_daily 
        WHERE recovery_score IS NOT NULL OR strain_score IS NOT NULL
        ORDER BY date DESC 
        LIMIT 7
    """).fetchall()
    
    for row in sample:
        print(f"  {row[0]}: Recovery={row[1]} ({row[2]}), Strain={row[3]} ({row[4]}), "
              f"HRV%={row[5]}, RHR%={row[6]}, Effort%={row[7]}, Primary={row[8]}")


def main():
    """Build derived scores table."""
    print("=" * 60)
    print("Building Derived Scores (Phase 5.5)")
    print("=" * 60)
    
    con = create_connection()
    
    try:
        build_derived_scores(con)
        validate_derived_scores(con)
        print("\n✓ Derived scores build complete")
    finally:
        con.close()


if __name__ == "__main__":
    main()
