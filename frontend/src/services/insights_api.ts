/**
 * API client for insights endpoints (Phase 5.5).
 * All backend calls for WHOOP-style cards are centralized here.
 */

import type {
  ScoresResponse,
  RecoveryVsStrainResponse,
  EffortCompositionResponse,
  ReadinessTimelineResponse,
} from '../types/insights';
import type { DailyMetricResponse } from './analytics_api';

const API_BASE = '/analytics';

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }
  return response.json();
}

export async function getScores(
  startDate: string,
  endDate: string
): Promise<ScoresResponse> {
  const params = new URLSearchParams({
    start_date: startDate,
    end_date: endDate,
  });
  return fetchJson<ScoresResponse>(`${API_BASE}/scores?${params}`);
}

export async function getRecoveryVsStrain(
  startDate: string,
  endDate: string
): Promise<RecoveryVsStrainResponse> {
  const params = new URLSearchParams({
    start_date: startDate,
    end_date: endDate,
  });
  return fetchJson<RecoveryVsStrainResponse>(`${API_BASE}/recovery-vs-strain?${params}`);
}

export async function getEffortComposition(
  startDate: string,
  endDate: string,
  granularity: 'day' | 'week' | 'month' = 'day'
): Promise<EffortCompositionResponse> {
  const params = new URLSearchParams({
    start_date: startDate,
    end_date: endDate,
    granularity,
  });
  return fetchJson<EffortCompositionResponse>(`${API_BASE}/effort-composition?${params}`);
}

export async function getReadinessTimeline(
  startDate: string,
  endDate: string
): Promise<ReadinessTimelineResponse> {
  const params = new URLSearchParams({
    start_date: startDate,
    end_date: endDate,
  });
  return fetchJson<ReadinessTimelineResponse>(`${API_BASE}/readiness-timeline?${params}`);
}

export async function getDailyMetricForInsights(
  metricKey: string,
  startDate: string,
  endDate: string
): Promise<DailyMetricResponse> {
  const params = new URLSearchParams({
    metric_key: metricKey,
    start_date: startDate,
    end_date: endDate,
  });
  return fetchJson<DailyMetricResponse>(`${API_BASE}/metric/daily?${params}`);
}
