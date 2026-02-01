/**
 * TypeScript types for insights API responses (Phase 5.5).
 * These match the backend Pydantic schemas exactly.
 */

// =============================================================================
// GET /analytics/scores
// =============================================================================

export interface Contributors {
  hrv_pct: number | null;
  rhr_pct: number | null;
  effort_pct: number | null;
}

export interface DataQuality {
  total_days: number;
  days_with_data: number;
  coverage_percent: number;
}

export interface DailyScore {
  date: string;
  recovery_score: number | null;
  recovery_label: string | null;
  recovery_color: string | null;
  strain_score: number | null;
  strain_label: string | null;
  strain_primary_metric: string | null;
  contributors: Contributors;
}

export interface ScoresResponse {
  start_date: string;
  end_date: string;
  scores: DailyScore[];
  data_quality: DataQuality;
}

// =============================================================================
// GET /analytics/recovery-vs-strain
// =============================================================================

export interface RecoveryStrainPoint {
  date: string;
  recovery_score: number;
  strain_score: number;
  recovery_color: string;
}

export interface RecoveryVsStrainResponse {
  start_date: string;
  end_date: string;
  points: RecoveryStrainPoint[];
  count: number;
}

// =============================================================================
// GET /analytics/effort-composition
// =============================================================================

export interface EffortBucket {
  period_start: string;
  steps: number | null;
  flights_climbed: number | null;
  active_energy: number | null;
  exercise_time: number | null;
  heart_rate_max: number | null;
  steps_pct: number | null;
  flights_pct: number | null;
  energy_pct: number | null;
  exercise_pct: number | null;
}

export interface EffortCompositionResponse {
  start_date: string;
  end_date: string;
  granularity: string;
  buckets: EffortBucket[];
  count: number;
}

// =============================================================================
// GET /analytics/readiness-timeline
// =============================================================================

export type AnnotationType = 
  | 'high_strain' 
  | 'low_hrv' 
  | 'high_rhr' 
  | 'recovery_up' 
  | 'recovery_down';

export interface TimelineDay {
  date: string;
  recovery_score: number | null;
  annotation: string | null;
  annotation_type: AnnotationType | null;
}

export interface ReadinessTimelineResponse {
  start_date: string;
  end_date: string;
  timeline: TimelineDay[];
  count: number;
}
