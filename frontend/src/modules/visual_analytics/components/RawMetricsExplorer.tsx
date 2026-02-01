/**
 * Raw Metrics Explorer (Advanced)
 * 
 * An advanced verification view showing raw daily metric values.
 * NOT an insight card - this is evidence, not interpretation.
 * 
 * Features:
 * - Metric selector (grouped by category)
 * - Per-card time range selector
 * - Absolute vs baseline-relative view toggle
 * - Preserves nulls as gaps
 * - Responds to date selections from other charts
 */

import { useState, useEffect, useMemo, useRef } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  ReferenceArea,
} from 'recharts';
import { ChevronDown, ChevronUp, Activity, Moon, Heart, Flame } from 'lucide-react';
import { colors, shadows } from '@/styles/theme';
import { getMetricsCatalog, getDailyMetric } from '@/services/analytics_api';
import type { MetricsCatalogResponse, DailyMetricPoint } from '@/services/analytics_api';
import { useSelectedDate } from '@/context';

type TimeRange = '1d' | '7d' | '30d' | '6m';
type ViewMode = 'absolute' | 'relative';
type MetricCategory = 'activity' | 'sleep' | 'recovery' | 'fitness';

interface MetricInfo {
  metric_key: string;
  display_name: string;
  unit: string;
  category: MetricCategory;
  is_sparse?: boolean;
}

interface ChartDataPoint {
  date: string;
  value: number | null;
  relativeValue: number | null;
  baselineMedian: number | null;
  baselineP25: number | null;
  baselineP75: number | null;
  anomalyLevel: string;
  isSelected: boolean;
}

const CATEGORY_ICONS: Record<MetricCategory, React.ReactNode> = {
  activity: <Activity size={14} />,
  sleep: <Moon size={14} />,
  recovery: <Heart size={14} />,
  fitness: <Flame size={14} />,
};

const CATEGORY_COLORS: Record<MetricCategory, string> = {
  activity: colors.metrics.steps,
  sleep: '#a78bfa',
  recovery: colors.metrics.hrv,
  fitness: colors.metrics.strain,
};

function getDateRange(range: TimeRange): { start: string; end: string } {
  const end = new Date();
  const start = new Date();
  
  switch (range) {
    case '1d':
      start.setDate(end.getDate() - 1);
      break;
    case '7d':
      start.setDate(end.getDate() - 7);
      break;
    case '30d':
      start.setDate(end.getDate() - 30);
      break;
    case '6m':
      start.setMonth(end.getMonth() - 6);
      break;
  }
  
  return {
    start: start.toISOString().split('T')[0],
    end: end.toISOString().split('T')[0],
  };
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function formatAxisDate(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

export function RawMetricsExplorer() {
  const [isExpanded, setIsExpanded] = useState(false);
  const [metrics, setMetrics] = useState<MetricInfo[]>([]);
  const [selectedMetric, setSelectedMetric] = useState<string>('steps');
  const [timeRange, setTimeRange] = useState<TimeRange>('30d');
  const [viewMode, setViewMode] = useState<ViewMode>('absolute');
  const [data, setData] = useState<DailyMetricPoint[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [metricInfo, setMetricInfo] = useState<MetricInfo | null>(null);
  const chartRef = useRef<HTMLDivElement>(null);
  
  const { selectedDate, setSelectedDate } = useSelectedDate();

  // Load metrics catalog
  useEffect(() => {
    getMetricsCatalog().then((res: MetricsCatalogResponse) => {
      const metricsList = res.metrics.map(m => ({
        ...m,
        category: (m.category || 'activity') as MetricCategory,
      }));
      setMetrics(metricsList);
      const defaultMetric = metricsList.find((m) => m.metric_key === 'steps') || metricsList[0];
      if (defaultMetric) {
        setSelectedMetric(defaultMetric.metric_key);
        setMetricInfo(defaultMetric);
      }
    });
  }, []);

  // Load metric data when selection changes
  useEffect(() => {
    if (!selectedMetric) return;
    
    const { start, end } = getDateRange(timeRange);
    setIsLoading(true);
    
    getDailyMetric(selectedMetric, start, end)
      .then((res) => {
        setData(res.data);
        const info = metrics.find((m) => m.metric_key === selectedMetric);
        setMetricInfo(info || null);
      })
      .finally(() => setIsLoading(false));
  }, [selectedMetric, timeRange, metrics]);

  // Check if baseline is available
  const hasBaseline = useMemo(() => {
    return data.some((d) => d.baseline_median !== null && d.baseline_median !== undefined);
  }, [data]);

  // Prepare chart data
  const chartData = useMemo<ChartDataPoint[]>(() => {
    return data.map((d) => {
      let relativeValue: number | null = null;
      const baselineMedian = d.baseline_median ?? null;
      if (d.value !== null && baselineMedian !== null && baselineMedian !== 0) {
        relativeValue = ((d.value - baselineMedian) / baselineMedian) * 100;
      }
      
      return {
        date: d.date,
        value: d.value,
        relativeValue,
        baselineMedian: d.baseline_median ?? null,
        baselineP25: d.baseline_p25 ?? null,
        baselineP75: d.baseline_p75 ?? null,
        anomalyLevel: d.anomaly_level,
        isSelected: d.date === selectedDate.date,
      };
    });
  }, [data, selectedDate.date]);

  // Group metrics by category
  const groupedMetrics = useMemo(() => {
    const groups: Record<MetricCategory, MetricInfo[]> = {
      activity: [],
      sleep: [],
      recovery: [],
      fitness: [],
    };
    
    metrics.forEach((m) => {
      if (groups[m.category]) {
        groups[m.category].push(m);
      }
    });
    
    return groups;
  }, [metrics]);

  // Get current metric color
  const lineColor = metricInfo ? CATEGORY_COLORS[metricInfo.category] : colors.metrics.steps;

  // Get Y-axis domain
  const yDomain = useMemo(() => {
    if (viewMode === 'relative') {
      const values = chartData.map((d) => d.relativeValue).filter((v) => v !== null) as number[];
      if (values.length === 0) return [-50, 50];
      const max = Math.max(...values.map(Math.abs), 20);
      return [-max * 1.1, max * 1.1];
    }
    
    const values = chartData.map((d) => d.value).filter((v) => v !== null) as number[];
    if (values.length === 0) return [0, 100];
    const min = Math.min(...values);
    const max = Math.max(...values);
    const padding = (max - min) * 0.1 || 10;
    return [Math.max(0, min - padding), max + padding];
  }, [chartData, viewMode]);

  // Get baseline band for absolute view
  const baselineBand = useMemo(() => {
    if (viewMode !== 'absolute') return null;
    const withBaseline = chartData.filter((d) => d.baselineP25 !== null && d.baselineP75 !== null);
    if (withBaseline.length === 0) return null;
    
    const p25 = withBaseline[0].baselineP25!;
    const p75 = withBaseline[0].baselineP75!;
    const median = withBaseline[0].baselineMedian;
    
    return { p25, p75, median };
  }, [chartData, viewMode]);

  // Custom tooltip
  const CustomTooltip = ({ active, payload }: { active?: boolean; payload?: Array<{ payload: ChartDataPoint }> }) => {
    if (!active || !payload?.[0]) return null;
    
    const d = payload[0].payload;
    const displayValue = viewMode === 'absolute' ? d.value : d.relativeValue;
    const unit = viewMode === 'absolute' ? (metricInfo?.unit || '') : '%';
    
    return (
      <div
        className="px-3 py-2 rounded-lg text-sm"
        style={{
          background: colors.bg.card,
          border: `1px solid ${colors.ui.border}`,
          boxShadow: shadows.card,
        }}
      >
        <div className="font-medium" style={{ color: colors.ui.text.primary }}>
          {formatDate(d.date)}
        </div>
        <div className="mt-1" style={{ color: lineColor }}>
          {displayValue !== null ? `${displayValue.toFixed(1)} ${unit}` : '—'}
        </div>
        {viewMode === 'absolute' && d.baselineMedian !== null && (
          <div className="mt-1" style={{ color: colors.ui.text.muted }}>
            Baseline: {d.baselineMedian.toFixed(1)} {metricInfo?.unit || ''}
          </div>
        )}
        {d.value !== null && d.baselineMedian !== null && viewMode === 'absolute' && (
          <div
            className="mt-1"
            style={{
              color: d.value >= d.baselineMedian ? colors.state.good : colors.state.warning,
            }}
          >
            {d.value >= d.baselineMedian ? '+' : ''}
            {(((d.value - d.baselineMedian) / d.baselineMedian) * 100).toFixed(1)}% vs baseline
          </div>
        )}
        {d.anomalyLevel !== 'none' && (
          <div className="mt-1" style={{ color: colors.state.warning }}>
            ⚠ {d.anomalyLevel} anomaly
          </div>
        )}
      </div>
    );
  };

  // Custom dot renderer for anomalies and selected date
  const renderDot = (props: { cx?: number; cy?: number; payload?: ChartDataPoint }) => {
    const { cx, cy, payload } = props;
    if (cx === undefined || cy === undefined || !payload || payload.value === null) return null;
    
    const isAnomaly = payload.anomalyLevel !== 'none';
    const isSelected = payload.isSelected;
    
    if (!isAnomaly && !isSelected) return null;
    
    return (
      <g key={payload.date}>
        {isSelected && (
          <>
            <circle cx={cx} cy={cy} r={12} fill="transparent" stroke={lineColor} strokeWidth={2} opacity={0.5} />
            <circle cx={cx} cy={cy} r={8} fill="transparent" stroke={lineColor} strokeWidth={1.5} />
          </>
        )}
        {isAnomaly && (
          <circle
            cx={cx}
            cy={cy}
            r={5}
            fill={payload.anomalyLevel === 'strong' ? colors.state.danger : colors.state.warning}
            style={{ filter: `drop-shadow(0 0 4px ${payload.anomalyLevel === 'strong' ? colors.state.danger : colors.state.warning})` }}
          />
        )}
      </g>
    );
  };

  // Handle chart click to select date
  const handleChartClick = (state: any) => {
    const payload = state?.activePayload?.[0]?.payload as ChartDataPoint | undefined;
    if (payload?.date) {
      setSelectedDate(payload.date, 'raw-metrics-explorer');
    }
  };

  // Disable relative view if no baseline
  const isRelativeDisabled = !hasBaseline;

  return (
    <div
      className="rounded-2xl overflow-hidden transition-all"
      style={{
        background: colors.bg.card,
        border: `1px solid ${colors.ui.border}`,
        boxShadow: shadows.card,
      }}
    >
      {/* Header - always visible */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between p-4 hover:bg-opacity-50 transition-colors"
        style={{ background: 'transparent' }}
      >
        <div className="flex items-center gap-3">
          <div
            className="px-2 py-0.5 rounded text-xs font-medium"
            style={{
              background: colors.bg.glass,
              color: colors.ui.text.muted,
            }}
          >
            Advanced
          </div>
          <div>
            <h3 className="text-left font-semibold" style={{ color: colors.ui.text.primary }}>
              Raw Metrics Explorer
            </h3>
            <p className="text-left text-sm" style={{ color: colors.ui.text.muted }}>
              View the underlying data used to compute your insights
            </p>
          </div>
        </div>
        <div style={{ color: colors.ui.text.secondary }}>
          {isExpanded ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
        </div>
      </button>

      {/* Expanded content */}
      {isExpanded && (
        <div className="px-4 pb-4 space-y-4">
          {/* Teaching line */}
          <p className="text-sm" style={{ color: colors.ui.text.muted }}>
            This chart shows the raw data used to compute your insights. Trends matter more than individual points.
          </p>

          {/* Controls row */}
          <div className="flex flex-wrap gap-4 items-center">
            {/* Metric selector */}
            <div className="flex-1 min-w-[200px]">
              <select
                value={selectedMetric}
                onChange={(e) => setSelectedMetric(e.target.value)}
                className="w-full px-3 py-2 rounded-lg text-sm transition-colors cursor-pointer"
                style={{
                  background: '#2a2a3a',
                  border: `1px solid ${colors.ui.border}`,
                  color: '#ffffff',
                  outline: 'none',
                }}
              >
                {Object.entries(groupedMetrics).map(([category, categoryMetrics]) => (
                  categoryMetrics.length > 0 && (
                    <optgroup 
                      key={category} 
                      label={category.charAt(0).toUpperCase() + category.slice(1)}
                      style={{ background: '#2a2a3a', color: '#ffffff' }}
                    >
                      {categoryMetrics.map((m) => (
                        <option 
                          key={m.metric_key} 
                          value={m.metric_key}
                          style={{ background: '#2a2a3a', color: '#ffffff', padding: '8px' }}
                        >
                          {m.display_name} {m.is_sparse ? '(Sparse)' : ''}
                        </option>
                      ))}
                    </optgroup>
                  )
                ))}
              </select>
            </div>

            {/* Time range selector */}
            <div
              className="flex rounded-lg overflow-hidden"
              style={{ border: `1px solid ${colors.ui.border}` }}
            >
              {(['1d', '7d', '30d', '6m'] as TimeRange[]).map((range) => (
                <button
                  key={range}
                  onClick={() => setTimeRange(range)}
                  className="px-3 py-1.5 text-sm font-medium transition-colors"
                  style={{
                    background: timeRange === range ? colors.ui.accent : 'transparent',
                    color: timeRange === range ? colors.ui.text.primary : colors.ui.text.muted,
                  }}
                >
                  {range.toUpperCase()}
                </button>
              ))}
            </div>

            {/* View toggle */}
            <div className="relative">
              <div
                className="flex rounded-lg overflow-hidden"
                style={{ border: `1px solid ${colors.ui.border}` }}
              >
                <button
                  onClick={() => setViewMode('absolute')}
                  className="px-3 py-1.5 text-sm font-medium transition-colors"
                  style={{
                    background: viewMode === 'absolute' ? colors.ui.accent : 'transparent',
                    color: viewMode === 'absolute' ? colors.ui.text.primary : colors.ui.text.muted,
                  }}
                >
                  Absolute
                </button>
                <button
                  onClick={() => !isRelativeDisabled && setViewMode('relative')}
                  className="px-3 py-1.5 text-sm font-medium transition-colors"
                  disabled={isRelativeDisabled}
                  title={isRelativeDisabled ? 'Baseline not available for this metric' : ''}
                  style={{
                    background: viewMode === 'relative' ? colors.ui.accent : 'transparent',
                    color: isRelativeDisabled
                      ? colors.ui.text.disabled
                      : viewMode === 'relative'
                        ? colors.ui.text.primary
                        : colors.ui.text.muted,
                    cursor: isRelativeDisabled ? 'not-allowed' : 'pointer',
                  }}
                >
                  Relative %
                </button>
              </div>
              {isRelativeDisabled && viewMode === 'absolute' && (
                <div
                  className="absolute top-full left-0 mt-1 text-xs whitespace-nowrap"
                  style={{ color: colors.ui.text.muted }}
                >
                  Baseline not available
                </div>
              )}
            </div>
          </div>

          {/* Metric info badge */}
          {metricInfo && (
            <div className="flex items-center gap-2">
              <span style={{ color: CATEGORY_COLORS[metricInfo.category] }}>
                {CATEGORY_ICONS[metricInfo.category]}
              </span>
              <span className="text-sm" style={{ color: colors.ui.text.secondary }}>
                {metricInfo.display_name}
              </span>
              <span
                className="px-2 py-0.5 rounded text-xs"
                style={{ background: colors.bg.glass, color: colors.ui.text.muted }}
              >
                {metricInfo.unit}
              </span>
              {metricInfo.is_sparse && (
                <span
                  className="px-2 py-0.5 rounded text-xs"
                  style={{ background: 'rgba(255, 184, 0, 0.2)', color: colors.state.warning }}
                >
                  Sparse
                </span>
              )}
            </div>
          )}

          {/* Chart */}
          <div ref={chartRef} className="h-64">
            {isLoading ? (
              <div
                className="h-full flex items-center justify-center"
                style={{ color: colors.ui.text.muted }}
              >
                Loading...
              </div>
            ) : chartData.length === 0 ? (
              <div
                className="h-full flex items-center justify-center"
                style={{ color: colors.ui.text.muted }}
              >
                No data available
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart
                  data={chartData}
                  onClick={handleChartClick}
                  margin={{ top: 10, right: 10, left: 10, bottom: 10 }}
                >
                  <defs>
                    <linearGradient id="lineGlow" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={lineColor} stopOpacity={0.8} />
                      <stop offset="100%" stopColor={lineColor} stopOpacity={0.2} />
                    </linearGradient>
                    <filter id="glow">
                      <feGaussianBlur stdDeviation="2" result="coloredBlur" />
                      <feMerge>
                        <feMergeNode in="coloredBlur" />
                        <feMergeNode in="SourceGraphic" />
                      </feMerge>
                    </filter>
                  </defs>

                  <XAxis
                    dataKey="date"
                    tickFormatter={formatAxisDate}
                    stroke={colors.ui.text.muted}
                    tick={{ fill: colors.ui.text.muted, fontSize: 11 }}
                    axisLine={{ stroke: colors.ui.border }}
                    tickLine={false}
                    interval="preserveStartEnd"
                  />
                  
                  <YAxis
                    domain={yDomain}
                    stroke={colors.ui.text.muted}
                    tick={{ fill: colors.ui.text.muted, fontSize: 11 }}
                    axisLine={{ stroke: colors.ui.border }}
                    tickLine={false}
                    tickFormatter={(v) =>
                      viewMode === 'relative' ? `${v > 0 ? '+' : ''}${v.toFixed(0)}%` : v.toFixed(0)
                    }
                    width={50}
                  />

                  {/* Baseline band (p25-p75) for absolute view */}
                  {baselineBand && viewMode === 'absolute' && (
                    <ReferenceArea
                      y1={baselineBand.p25}
                      y2={baselineBand.p75}
                      fill={colors.metrics.baseline}
                      fillOpacity={0.3}
                    />
                  )}

                  {/* Baseline median line for absolute view */}
                  {baselineBand && baselineBand.median !== null && viewMode === 'absolute' && (
                    <ReferenceLine
                      y={baselineBand.median}
                      stroke={colors.ui.text.muted}
                      strokeDasharray="4 4"
                      strokeOpacity={0.5}
                    />
                  )}

                  {/* Zero line for relative view */}
                  {viewMode === 'relative' && (
                    <ReferenceLine
                      y={0}
                      stroke={colors.ui.text.muted}
                      strokeDasharray="4 4"
                      strokeOpacity={0.5}
                    />
                  )}

                  <Tooltip content={<CustomTooltip />} />

                  <Line
                    type="monotone"
                    dataKey={viewMode === 'absolute' ? 'value' : 'relativeValue'}
                    stroke={lineColor}
                    strokeWidth={2}
                    dot={renderDot}
                    activeDot={{ r: 6, fill: lineColor, stroke: colors.bg.primary, strokeWidth: 2 }}
                    connectNulls={false}
                    filter="url(#glow)"
                  />
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>

          {/* Legend */}
          <div className="flex flex-wrap gap-4 text-xs" style={{ color: colors.ui.text.muted }}>
            {viewMode === 'absolute' && hasBaseline && (
              <div className="flex items-center gap-2">
                <div
                  className="w-8 h-3 rounded"
                  style={{ background: colors.metrics.baseline, opacity: 0.5 }}
                />
                <span>Baseline range (p25–p75)</span>
              </div>
            )}
            <div className="flex items-center gap-2">
              <div
                className="w-3 h-3 rounded-full"
                style={{ background: colors.state.warning }}
              />
              <span>Anomaly</span>
            </div>
            {selectedDate.date && (
              <div className="flex items-center gap-2">
                <div
                  className="w-3 h-3 rounded-full border-2"
                  style={{ borderColor: lineColor, background: 'transparent' }}
                />
                <span>Selected date</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
