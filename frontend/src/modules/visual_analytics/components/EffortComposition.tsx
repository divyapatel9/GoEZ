/**
 * Effort Composition - Premium Redesign
 * 
 * Features:
 * - Stacked bar chart with icons per component
 * - Absolute vs Percent toggle
 * - Component colors with glow effects
 * - Rich tooltips with absolute + percent values
 */

import { useState, useEffect, useMemo } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { GlassCard, CardHeader, TeachingLine, CardTimeSelector, getDateRangeFromPreset } from '@/shared/ui';
import type { TimeRange } from '@/shared/ui';
import { colors } from '@/styles/theme';
import type { EffortBucket } from '@/types/insights';
import { getEffortComposition } from '@/services/insights_api';

interface EffortCompositionProps {
  initialRange?: TimeRange;
}

const COMPONENTS = [
  { key: 'steps', label: 'Steps', icon: '👟', color: '#3b82f6' },
  { key: 'flights', label: 'Flights', icon: '🪜', color: '#8b5cf6' },
  { key: 'energy', label: 'Active Energy', icon: '🔥', color: '#f59e0b' },
  { key: 'exercise', label: 'Exercise', icon: '💪', color: '#10b981' },
];

function formatPeriod(dateStr: string, granularity: string): string {
  const date = new Date(dateStr);
  if (granularity === 'day') {
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  } else if (granularity === 'week') {
    return `W${Math.ceil(date.getDate() / 7)}`;
  } else {
    return date.toLocaleDateString('en-US', { month: 'short' });
  }
}

function formatValue(value: number | null, type: string): string {
  if (value === null) return '—';
  switch (type) {
    case 'steps':
      return value >= 1000 ? `${(value / 1000).toFixed(1)}k` : value.toFixed(0);
    case 'flights':
      return value.toFixed(0);
    case 'energy':
      return `${value.toFixed(0)} kcal`;
    case 'exercise':
      return `${value.toFixed(0)} min`;
    default:
      return value.toFixed(0);
  }
}

function getGranularity(range: TimeRange): 'day' | 'week' | 'month' {
  switch (range) {
    case '1d': return 'day';
    case '7d': return 'day';
    case '30d': return 'week';
    case '6m': return 'month';
    default: return 'day';
  }
}

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload || !payload.length) return null;

  const bucket = payload[0]?.payload;
  if (!bucket) return null;

  const total = (bucket.steps || 0) + (bucket.flights_climbed || 0) + (bucket.active_energy || 0) + (bucket.exercise_time || 0);

  return (
    <div
      className="px-4 py-3 rounded-xl"
      style={{
        background: colors.bg.card,
        border: `1px solid ${colors.ui.border}`,
        boxShadow: '0 4px 20px rgba(0,0,0,0.5)',
      }}
    >
      <p className="font-semibold mb-3" style={{ color: colors.ui.text.primary }}>
        {label}
      </p>

      <div className="space-y-2">
        {COMPONENTS.map(comp => {
          const rawKey = comp.key === 'flights' ? 'flights_climbed' : comp.key === 'energy' ? 'active_energy' : comp.key === 'exercise' ? 'exercise_time' : comp.key;
          const value = bucket[rawKey];
          const pct = total > 0 && value ? ((value / total) * 100).toFixed(1) : '0';

          return (
            <div key={comp.key} className="flex items-center gap-2">
              <span className="text-sm">{comp.icon}</span>
              <div
                className="w-3 h-3 rounded"
                style={{ background: comp.color }}
              />
              <span className="text-xs" style={{ color: colors.ui.text.secondary }}>
                {comp.label}:
              </span>
              <span className="font-semibold text-xs" style={{ color: comp.color }}>
                {formatValue(value, comp.key)}
              </span>
              <span className="text-xs" style={{ color: colors.ui.text.muted }}>
                ({pct}%)
              </span>
            </div>
          );
        })}
      </div>

      {bucket.heart_rate_max && (
        <div 
          className="mt-3 pt-2 text-xs"
          style={{ 
            borderTop: `1px solid ${colors.ui.border}`,
            color: colors.ui.text.muted 
          }}
        >
          Peak HR: {bucket.heart_rate_max.toFixed(0)} bpm
        </div>
      )}
    </div>
  );
}

export function EffortComposition({ initialRange = '30d' }: EffortCompositionProps) {
  const [timeRange, setTimeRange] = useState<TimeRange>(initialRange);
  const [buckets, setBuckets] = useState<EffortBucket[]>([]);
  const [showPercent, setShowPercent] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  const granularity = getGranularity(timeRange);

  useEffect(() => {
    async function loadData() {
      setIsLoading(true);
      try {
        const { start, end } = getDateRangeFromPreset(timeRange);
        const response = await getEffortComposition(start, end, granularity);
        setBuckets(response.buckets);
      } catch (err) {
        console.error('Failed to load effort data:', err);
      } finally {
        setIsLoading(false);
      }
    }
    loadData();
  }, [timeRange, granularity]);

  const chartData = useMemo(() => {
    return buckets.map(b => {
      const total = (b.steps || 0) + (b.flights_climbed || 0) + (b.active_energy || 0) + (b.exercise_time || 0);
      return {
        ...b,
        period: formatPeriod(b.period_start, granularity),
        stepsNorm: showPercent ? (total > 0 ? ((b.steps || 0) / total) * 100 : 0) : (b.steps || 0),
        flightsNorm: showPercent ? (total > 0 ? ((b.flights_climbed || 0) / total) * 100 : 0) : (b.flights_climbed || 0),
        energyNorm: showPercent ? (total > 0 ? ((b.active_energy || 0) / total) * 100 : 0) : (b.active_energy || 0),
        exerciseNorm: showPercent ? (total > 0 ? ((b.exercise_time || 0) / total) * 100 : 0) : (b.exercise_time || 0),
      };
    });
  }, [buckets, showPercent, granularity]);

  const totals = useMemo(() => {
    return buckets.reduce((acc, b) => ({
      steps: acc.steps + (b.steps || 0),
      flights: acc.flights + (b.flights_climbed || 0),
      energy: acc.energy + (b.active_energy || 0),
      exercise: acc.exercise + (b.exercise_time || 0),
    }), { steps: 0, flights: 0, energy: 0, exercise: 0 });
  }, [buckets]);

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
        title="Effort Composition"
        subtitle="Where your strain came from"
        rightContent={
          <div className="flex items-center gap-3">
            <div 
              className="flex items-center rounded-lg p-0.5"
              style={{ background: colors.bg.glass, border: `1px solid ${colors.ui.border}` }}
            >
              <button
                onClick={() => setShowPercent(false)}
                className="px-2 py-1 text-xs font-medium rounded-md transition-all"
                style={{
                  background: !showPercent ? colors.ui.accent : 'transparent',
                  color: !showPercent ? colors.ui.text.primary : colors.ui.text.muted,
                }}
              >
                Absolute
              </button>
              <button
                onClick={() => setShowPercent(true)}
                className="px-2 py-1 text-xs font-medium rounded-md transition-all"
                style={{
                  background: showPercent ? colors.ui.accent : 'transparent',
                  color: showPercent ? colors.ui.text.primary : colors.ui.text.muted,
                }}
              >
                Percent
              </button>
            </div>
            <CardTimeSelector value={timeRange} onChange={setTimeRange} compact />
          </div>
        }
      />

      {buckets.length === 0 ? (
        <div
          className="h-72 flex items-center justify-center"
          style={{ color: colors.ui.text.muted }}
        >
          No effort data available
        </div>
      ) : (
        <>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
              <defs>
                {COMPONENTS.map(comp => (
                  <linearGradient key={comp.key} id={`grad-${comp.key}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={comp.color} stopOpacity={1} />
                    <stop offset="100%" stopColor={comp.color} stopOpacity={0.6} />
                  </linearGradient>
                ))}
              </defs>

              <CartesianGrid strokeDasharray="3 3" stroke={colors.ui.border} />

              <XAxis
                dataKey="period"
                tick={{ fill: colors.ui.text.muted, fontSize: 10 }}
                tickLine={false}
                axisLine={{ stroke: colors.ui.border }}
              />

              <YAxis
                tick={{ fill: colors.ui.text.muted, fontSize: 10 }}
                tickLine={false}
                axisLine={{ stroke: colors.ui.border }}
                tickFormatter={(v) => showPercent ? `${v}%` : (v >= 1000 ? `${(v / 1000).toFixed(0)}k` : v)}
              />

              <Tooltip content={<CustomTooltip />} />

              <Bar dataKey="stepsNorm" stackId="a" fill="url(#grad-steps)" />
              <Bar dataKey="flightsNorm" stackId="a" fill="url(#grad-flights)" />
              <Bar dataKey="energyNorm" stackId="a" fill="url(#grad-energy)" />
              <Bar dataKey="exerciseNorm" stackId="a" fill="url(#grad-exercise)" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>

          <div 
            className="grid grid-cols-4 gap-4 mt-4 pt-4"
            style={{ borderTop: `1px solid ${colors.ui.border}` }}
          >
            {COMPONENTS.map(comp => {
              const value = totals[comp.key as keyof typeof totals];
              return (
                <div key={comp.key} className="text-center">
                  <div className="flex items-center justify-center gap-1 mb-1">
                    <span className="text-sm">{comp.icon}</span>
                    <div className="w-2 h-2 rounded" style={{ background: comp.color }} />
                  </div>
                  <p className="text-xs" style={{ color: colors.ui.text.muted }}>{comp.label}</p>
                  <p className="font-semibold text-sm" style={{ color: comp.color }}>
                    {formatValue(value, comp.key)}
                  </p>
                </div>
              );
            })}
          </div>
        </>
      )}

      <TeachingLine
        text="This shows what contributed most to your daily strain — workouts, daily movement, stairs, or intensity."
        direction="higher"
      />
    </GlassCard>
  );
}
