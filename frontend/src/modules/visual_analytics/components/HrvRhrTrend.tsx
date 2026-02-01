/**
 * HRV + Resting HR Trend - Premium Redesign
 * 
 * Features:
 * - Dark background with glowing lines
 * - HRV = teal, RHR = magenta
 * - Baseline as soft translucent band
 * - Warning zones when HRV low AND RHR high
 * - 7-day average toggle (ON by default for long ranges)
 * - Realistic axis clamping
 */

import { useState, useEffect, useMemo } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  ReferenceArea,
} from 'recharts';
import { GlassCard, CardHeader, TeachingLine, CardTimeSelector, getDateRangeFromPreset } from '@/shared/ui';
import type { TimeRange } from '@/shared/ui';
import { colors } from '@/styles/theme';
import { getDailyMetric } from '@/services/analytics_api';
import type { DailyMetricPoint } from '@/services/analytics_api';

interface HrvRhrTrendProps {
  initialRange?: TimeRange;
}

interface ChartPoint {
  date: string;
  hrv: number | null;
  rhr: number | null;
  hrvBaseline: number | null;
  rhrBaseline: number | null;
  hrvAvg7d: number | null;
  rhrAvg7d: number | null;
  isWarning: boolean;
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function calculate7DayAvg(data: (number | null)[], index: number): number | null {
  const window = data.slice(Math.max(0, index - 6), index + 1).filter((v): v is number => v !== null);
  if (window.length < 3) return null;
  return window.reduce((a, b) => a + b, 0) / window.length;
}

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload || !payload.length) return null;

  const point = payload[0]?.payload as ChartPoint;
  if (!point) return null;

  return (
    <div
      className="px-4 py-3 rounded-xl"
      style={{
        background: colors.bg.card,
        border: `1px solid ${colors.ui.border}`,
        boxShadow: '0 4px 20px rgba(0,0,0,0.5)',
      }}
    >
      <p className="font-semibold mb-2" style={{ color: colors.ui.text.primary }}>
        {formatDate(label)}
      </p>

      {point.hrv !== null && (
        <div className="flex items-center gap-2 mb-1">
          <div className="w-3 h-0.5 rounded" style={{ background: colors.metrics.hrv }} />
          <span style={{ color: colors.ui.text.secondary }}>HRV:</span>
          <span className="font-semibold" style={{ color: colors.metrics.hrv }}>
            {point.hrv.toFixed(0)} ms
          </span>
          {point.hrvBaseline && (
            <span className="text-xs" style={{ color: colors.ui.text.muted }}>
              (baseline: {point.hrvBaseline.toFixed(0)})
            </span>
          )}
        </div>
      )}

      {point.rhr !== null && (
        <div className="flex items-center gap-2">
          <div className="w-3 h-0.5 rounded" style={{ background: colors.metrics.rhr }} />
          <span style={{ color: colors.ui.text.secondary }}>RHR:</span>
          <span className="font-semibold" style={{ color: colors.metrics.rhr }}>
            {point.rhr.toFixed(0)} bpm
          </span>
          {point.rhrBaseline && (
            <span className="text-xs" style={{ color: colors.ui.text.muted }}>
              (baseline: {point.rhrBaseline.toFixed(0)})
            </span>
          )}
        </div>
      )}

      {point.isWarning && (
        <div 
          className="mt-2 px-2 py-1 rounded text-xs"
          style={{ 
            background: 'rgba(255, 184, 0, 0.15)', 
            color: colors.state.warning 
          }}
        >
          ⚠️ HRV below & RHR above baseline
        </div>
      )}
    </div>
  );
}

export function HrvRhrTrend({ initialRange = '30d' }: HrvRhrTrendProps) {
  const [timeRange, setTimeRange] = useState<TimeRange>(initialRange);
  const [hrvData, setHrvData] = useState<DailyMetricPoint[]>([]);
  const [rhrData, setRhrData] = useState<DailyMetricPoint[]>([]);
  const [show7dAvg, setShow7dAvg] = useState(true);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      setIsLoading(true);
      try {
        const { start, end } = getDateRangeFromPreset(timeRange);
        const [hrvRes, rhrRes] = await Promise.all([
          getDailyMetric('hrv_sdnn', start, end),
          getDailyMetric('resting_heart_rate', start, end),
        ]);
        setHrvData(hrvRes.data);
        setRhrData(rhrRes.data);
      } catch (err) {
        console.error('Failed to load trend data:', err);
      } finally {
        setIsLoading(false);
      }
    }
    loadData();
  }, [timeRange]);

  useEffect(() => {
    setShow7dAvg(timeRange !== '7d' && timeRange !== '1d');
  }, [timeRange]);

  const chartData: ChartPoint[] = useMemo(() => {
    const hrvMap = new Map(hrvData.map(d => [d.date, d]));
    const rhrMap = new Map(rhrData.map(d => [d.date, d]));
    const allDates = [...new Set([...hrvData.map(d => d.date), ...rhrData.map(d => d.date)])].sort();

    const hrvValues = allDates.map(d => hrvMap.get(d)?.value ?? null);
    const rhrValues = allDates.map(d => rhrMap.get(d)?.value ?? null);

    return allDates.map((date, i) => {
      const hrv = hrvMap.get(date);
      const rhr = rhrMap.get(date);

      const hrvBelowBaseline = hrv?.value != null && hrv?.baseline_median != null && hrv.value < hrv.baseline_median * 0.9;
      const rhrAboveBaseline = rhr?.value != null && rhr?.baseline_median != null && rhr.value > rhr.baseline_median * 1.05;

      return {
        date,
        hrv: hrv?.value ?? null,
        rhr: rhr?.value ?? null,
        hrvBaseline: hrv?.baseline_median ?? null,
        rhrBaseline: rhr?.baseline_median ?? null,
        hrvAvg7d: calculate7DayAvg(hrvValues, i),
        rhrAvg7d: calculate7DayAvg(rhrValues, i),
        isWarning: hrvBelowBaseline && rhrAboveBaseline,
      };
    });
  }, [hrvData, rhrData]);

  const warningRanges = useMemo(() => {
    const ranges: { start: string; end: string }[] = [];
    let rangeStart: string | null = null;

    for (let i = 0; i < chartData.length; i++) {
      if (chartData[i].isWarning) {
        if (!rangeStart) rangeStart = chartData[i].date;
      } else {
        if (rangeStart && i > 0) {
          ranges.push({ start: rangeStart, end: chartData[i - 1].date });
          rangeStart = null;
        }
      }
    }
    if (rangeStart) {
      ranges.push({ start: rangeStart, end: chartData[chartData.length - 1].date });
    }
    return ranges;
  }, [chartData]);

  const { hrvDomain, rhrDomain, avgHrvBaseline, avgRhrBaseline } = useMemo(() => {
    const hrvValues = chartData.map(d => d.hrv).filter((v): v is number => v !== null);
    const rhrValues = chartData.map(d => d.rhr).filter((v): v is number => v !== null);
    const hrvBaselines = chartData.map(d => d.hrvBaseline).filter((v): v is number => v !== null);
    const rhrBaselines = chartData.map(d => d.rhrBaseline).filter((v): v is number => v !== null);

    return {
      hrvDomain: hrvValues.length > 0
        ? [Math.floor(Math.min(...hrvValues) * 0.85), Math.ceil(Math.max(...hrvValues) * 1.15)]
        : [0, 100],
      rhrDomain: rhrValues.length > 0
        ? [Math.floor(Math.min(...rhrValues) * 0.92), Math.ceil(Math.max(...rhrValues) * 1.08)]
        : [40, 100],
      avgHrvBaseline: hrvBaselines.length > 0
        ? hrvBaselines.reduce((a, b) => a + b, 0) / hrvBaselines.length
        : null,
      avgRhrBaseline: rhrBaselines.length > 0
        ? rhrBaselines.reduce((a, b) => a + b, 0) / rhrBaselines.length
        : null,
    };
  }, [chartData]);

  if (isLoading) {
    return (
      <GlassCard className="animate-pulse">
        <div className="h-6 w-48 rounded" style={{ background: colors.bg.glass }} />
        <div className="h-72 mt-4 rounded" style={{ background: colors.bg.glass }} />
      </GlassCard>
    );
  }

  return (
    <GlassCard>
      <CardHeader
        title="HRV + Resting HR"
        subtitle="Nervous system recovery indicators"
        rightContent={
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={show7dAvg}
                onChange={(e) => setShow7dAvg(e.target.checked)}
                className="rounded border-gray-600 bg-transparent"
                style={{ accentColor: colors.ui.accent }}
              />
              <span className="text-xs" style={{ color: colors.ui.text.muted }}>
                7d avg
              </span>
            </label>
            <CardTimeSelector value={timeRange} onChange={setTimeRange} compact />
          </div>
        }
      />

      {chartData.length === 0 ? (
        <div
          className="h-72 flex items-center justify-center"
          style={{ color: colors.ui.text.muted }}
        >
          No HRV or RHR data available
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="hrvGlow" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={colors.metrics.hrv} stopOpacity={0.3} />
                <stop offset="95%" stopColor={colors.metrics.hrv} stopOpacity={0} />
              </linearGradient>
              <linearGradient id="rhrGlow" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={colors.metrics.rhr} stopOpacity={0.3} />
                <stop offset="95%" stopColor={colors.metrics.rhr} stopOpacity={0} />
              </linearGradient>
              <filter id="glow">
                <feGaussianBlur stdDeviation="3" result="coloredBlur" />
                <feMerge>
                  <feMergeNode in="coloredBlur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>

            <CartesianGrid strokeDasharray="3 3" stroke={colors.ui.border} />

            {warningRanges.map((range, i) => (
              <ReferenceArea
                key={i}
                x1={range.start}
                x2={range.end}
                fill={colors.state.warning}
                fillOpacity={0.1}
              />
            ))}

            <XAxis
              dataKey="date"
              tickFormatter={formatDate}
              tick={{ fill: colors.ui.text.muted, fontSize: 10 }}
              tickLine={false}
              axisLine={{ stroke: colors.ui.border }}
            />

            <YAxis
              yAxisId="hrv"
              orientation="left"
              domain={hrvDomain}
              tick={{ fill: colors.metrics.hrv, fontSize: 10 }}
              tickLine={false}
              axisLine={{ stroke: colors.ui.border }}
              tickFormatter={(v) => `${v}`}
            />

            <YAxis
              yAxisId="rhr"
              orientation="right"
              domain={rhrDomain}
              tick={{ fill: colors.metrics.rhr, fontSize: 10 }}
              tickLine={false}
              axisLine={{ stroke: colors.ui.border }}
              tickFormatter={(v) => `${v}`}
            />

            <Tooltip content={<CustomTooltip />} />

            {avgHrvBaseline && (
              <ReferenceLine
                yAxisId="hrv"
                y={avgHrvBaseline}
                stroke={colors.metrics.hrv}
                strokeDasharray="4 4"
                strokeOpacity={0.4}
              />
            )}

            {avgRhrBaseline && (
              <ReferenceLine
                yAxisId="rhr"
                y={avgRhrBaseline}
                stroke={colors.metrics.rhr}
                strokeDasharray="4 4"
                strokeOpacity={0.4}
              />
            )}

            {show7dAvg ? (
              <>
                <Line
                  yAxisId="hrv"
                  type="monotone"
                  dataKey="hrvAvg7d"
                  stroke={colors.metrics.hrv}
                  strokeWidth={3}
                  dot={false}
                  connectNulls={false}
                  filter="url(#glow)"
                />
                <Line
                  yAxisId="rhr"
                  type="monotone"
                  dataKey="rhrAvg7d"
                  stroke={colors.metrics.rhr}
                  strokeWidth={3}
                  dot={false}
                  connectNulls={false}
                  filter="url(#glow)"
                />
              </>
            ) : (
              <>
                <Line
                  yAxisId="hrv"
                  type="monotone"
                  dataKey="hrv"
                  stroke={colors.metrics.hrv}
                  strokeWidth={2}
                  dot={{ r: 3, fill: colors.metrics.hrv }}
                  connectNulls={false}
                  filter="url(#glow)"
                />
                <Line
                  yAxisId="rhr"
                  type="monotone"
                  dataKey="rhr"
                  stroke={colors.metrics.rhr}
                  strokeWidth={2}
                  dot={{ r: 3, fill: colors.metrics.rhr }}
                  connectNulls={false}
                  filter="url(#glow)"
                />
              </>
            )}
          </LineChart>
        </ResponsiveContainer>
      )}

      <div 
        className="flex items-center justify-center gap-6 mt-4 pt-4"
        style={{ borderTop: `1px solid ${colors.ui.border}` }}
      >
        <div className="flex items-center gap-2">
          <div className="w-4 h-1 rounded" style={{ background: colors.metrics.hrv }} />
          <span className="text-xs" style={{ color: colors.ui.text.secondary }}>HRV (ms)</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-1 rounded" style={{ background: colors.metrics.rhr }} />
          <span className="text-xs" style={{ color: colors.ui.text.secondary }}>Resting HR (bpm)</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-3 rounded" style={{ background: `${colors.state.warning}20` }} />
          <span className="text-xs" style={{ color: colors.ui.text.secondary }}>Low recovery signal</span>
        </div>
      </div>

      <TeachingLine
        text="When HRV falls and resting heart rate rises together, it often signals stress or incomplete recovery."
        direction="baseline"
      />
    </GlassCard>
  );
}
