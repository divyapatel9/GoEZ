/**
 * Analytics API service - calls /analytics/* endpoints
 */

const API_BASE = '/analytics'

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url)
  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`)
  }
  return response.json()
}

// Types
export interface MetricInfo {
  metric_key: string
  display_name: string
  unit: string
  category: string
  is_sparse?: boolean
  supports_anomalies?: boolean
  supports_correlations?: boolean
}

export interface MetricsCatalogResponse {
  metrics: MetricInfo[]
  count: number
}

export interface DailyMetricPoint {
  date: string
  value: number | null
  unit: string
  baseline_p25?: number
  baseline_p75?: number
  baseline_median?: number
  anomaly_level: 'none' | 'mild' | 'strong'
}

export interface DailyMetricResponse {
  metric_key: string
  display_name: string
  unit: string
  start_date: string
  end_date: string
  data: DailyMetricPoint[]
  count: number
}

export interface OverviewTile {
  metric_key: string
  display_name: string
  latest_value: number
  latest_date: string
  unit: string
  baseline_median?: number
  delta_vs_baseline?: number
  delta_percent?: number
  trend_7d: 'up' | 'down' | 'flat'
  anomaly_level: 'none' | 'mild' | 'strong'
}

export interface OverviewResponse {
  as_of_date: string
  tiles: OverviewTile[]
  count: number
}

export interface DailyScore {
  date: string
  recovery_score?: number
  recovery_label?: string
  recovery_color?: string
  strain_score?: number
  strain_label?: string
  strain_primary_metric?: string
  contributors: {
    hrv_pct?: number
    rhr_pct?: number
    effort_pct?: number
  }
}

export interface ScoresResponse {
  start_date: string
  end_date: string
  scores: DailyScore[]
  data_quality: {
    total_days: number
    days_with_data: number
    coverage_percent: number
  }
}

// API Functions
export async function getMetricsCatalog(): Promise<MetricsCatalogResponse> {
  return fetchJson<MetricsCatalogResponse>(`${API_BASE}/metrics`)
}

export async function getDailyMetric(
  metricKey: string,
  startDate: string,
  endDate: string
): Promise<DailyMetricResponse> {
  const params = new URLSearchParams({
    metric_key: metricKey,
    start_date: startDate,
    end_date: endDate,
  })
  return fetchJson<DailyMetricResponse>(`${API_BASE}/metric/daily?${params}`)
}

export async function getOverview(endDate?: string): Promise<OverviewResponse> {
  const params = endDate ? `?end_date=${endDate}` : ''
  return fetchJson<OverviewResponse>(`${API_BASE}/overview${params}`)
}

export async function getScores(startDate: string, endDate: string): Promise<ScoresResponse> {
  const params = new URLSearchParams({ start_date: startDate, end_date: endDate })
  return fetchJson<ScoresResponse>(`${API_BASE}/scores?${params}`)
}

export async function checkHealth(): Promise<{ status: string }> {
  return fetchJson<{ status: string }>(`/health`)
}

// Chart context types for AI explanations
export interface TimeSeriesSummary {
  last_n_days: number
  values: (number | null)[]
  dates: string[]
  min_value: number | null
  max_value: number | null
  mean_value: number | null
}

export interface BaselineSummary {
  current_median: number | null
  current_p25: number | null
  current_p75: number | null
  has_baseline: boolean
}

export interface AnomalyItem {
  date: string
  metric_key: string
  display_name: string
  value: number
  baseline_median: number | null
  anomaly_level: 'none' | 'mild' | 'strong'
  reason: string
}

export interface AnomalySummary {
  total_count: number
  mild_count: number
  strong_count: number
  recent_anomalies: AnomalyItem[]
}

export interface CorrelationItem {
  metric_a: string
  metric_b: string
  metric_a_display: string
  metric_b_display: string
  lag_days: number
  corr: number
  n: number
  interpretation: string
}

export interface DataQualityIndicators {
  total_days: number
  days_with_data: number
  coverage_percent: number
  avg_sample_count: number | null
}

export interface ChartContextResponse {
  metric_key: string
  display_name: string
  unit: string
  category: string
  start_date: string
  end_date: string
  focus_date: string | null
  time_series: TimeSeriesSummary
  baseline: BaselineSummary
  anomalies: AnomalySummary
  correlations: CorrelationItem[]
  data_quality: DataQualityIndicators
}

export async function getChartContext(
  metricKey: string,
  startDate: string,
  endDate: string,
  focusDate?: string
): Promise<ChartContextResponse> {
  const params = new URLSearchParams({
    metric_key: metricKey,
    start_date: startDate,
    end_date: endDate,
  })
  if (focusDate) {
    params.append('focus_date', focusDate)
  }
  return fetchJson<ChartContextResponse>(`${API_BASE}/chart-context?${params}`)
}
