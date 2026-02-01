/**
 * Movement Efficiency Card - New Insight
 * 
 * Compares Steps + Distance + Active Energy
 * Visual: Scatter plot with diagonal efficiency bands
 * Teaching: "Higher energy per distance means more intense movement."
 */

import { useState, useEffect, useMemo } from 'react';
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Cell,
} from 'recharts';
import { GlassCard, CardHeader, TeachingLine, InsightBadge, CardTimeSelector, getDateRangeFromPreset } from '@/shared/ui';
import type { TimeRange } from '@/shared/ui';
import { colors } from '@/styles/theme';
import { getDailyMetric } from '@/services/analytics_api';

interface MovementEfficiencyProps {
  initialRange?: TimeRange;
}

interface EfficiencyPoint {
  date: string;
  distance: number;
  energy: number;
  steps: number;
  efficiency: number;
  isToday: boolean;
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function getEfficiencyColor(efficiency: number): string {
  if (efficiency >= 1.2) return colors.state.good;
  if (efficiency >= 0.8) return colors.state.warning;
  return colors.state.danger;
}

function CustomTooltip({ active, payload }: any) {
  if (!active || !payload || !payload.length) return null;

  const point = payload[0].payload as EfficiencyPoint;
  const effColor = getEfficiencyColor(point.efficiency);

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
        {point.isToday ? '📍 Today' : formatDate(point.date)}
      </p>

      <div className="space-y-1 text-sm">
        <div className="flex justify-between gap-4">
          <span style={{ color: colors.ui.text.muted }}>Distance:</span>
          <span style={{ color: colors.metrics.steps }}>{point.distance.toFixed(2)} km</span>
        </div>
        <div className="flex justify-between gap-4">
          <span style={{ color: colors.ui.text.muted }}>Energy:</span>
          <span style={{ color: colors.metrics.energy }}>{point.energy.toFixed(0)} kcal</span>
        </div>
        <div className="flex justify-between gap-4">
          <span style={{ color: colors.ui.text.muted }}>Steps:</span>
          <span style={{ color: colors.ui.text.secondary }}>{point.steps.toLocaleString()}</span>
        </div>
      </div>

      <div 
        className="mt-2 pt-2 flex justify-between items-center"
        style={{ borderTop: `1px solid ${colors.ui.border}` }}
      >
        <span style={{ color: colors.ui.text.muted }}>Efficiency:</span>
        <span className="font-bold" style={{ color: effColor }}>
          {(point.efficiency * 100).toFixed(0)}%
        </span>
      </div>
    </div>
  );
}

export function MovementEfficiency({ initialRange = '30d' }: MovementEfficiencyProps) {
  const [timeRange, setTimeRange] = useState<TimeRange>(initialRange);
  const [data, setData] = useState<EfficiencyPoint[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      setIsLoading(true);
      try {
        const { start, end } = getDateRangeFromPreset(timeRange);
        const [distanceRes, energyRes, stepsRes] = await Promise.all([
          getDailyMetric('distance_walking_running', start, end),
          getDailyMetric('active_energy', start, end),
          getDailyMetric('steps', start, end),
        ]);

        const distanceMap = new Map(distanceRes.data.map(d => [d.date, d.value]));
        const energyMap = new Map(energyRes.data.map(d => [d.date, d.value]));
        const stepsMap = new Map(stepsRes.data.map(d => [d.date, d.value]));

        const allDates = [...new Set([
          ...distanceRes.data.map(d => d.date),
          ...energyRes.data.map(d => d.date),
        ])].sort();

        const points: EfficiencyPoint[] = allDates
          .map((date, i) => {
            const distance = distanceMap.get(date);
            const energy = energyMap.get(date);
            const steps = stepsMap.get(date);

            if (!distance || !energy || distance <= 0) return null;

            const efficiency = energy / (distance * 50);

            return {
              date,
              distance,
              energy,
              steps: steps || 0,
              efficiency,
              isToday: i === allDates.length - 1,
            };
          })
          .filter((p): p is EfficiencyPoint => p !== null);

        setData(points);
      } catch (err) {
        console.error('Failed to load efficiency data:', err);
      } finally {
        setIsLoading(false);
      }
    }
    loadData();
  }, [timeRange]);

  const stats = useMemo(() => {
    if (data.length === 0) return null;
    
    const avgEfficiency = data.reduce((sum, d) => sum + d.efficiency, 0) / data.length;
    const highEffDays = data.filter(d => d.efficiency >= 1.2).length;
    
    return { avgEfficiency, highEffDays };
  }, [data]);

  const todayPoint = data.find(d => d.isToday);

  if (isLoading) {
    return (
      <GlassCard className="animate-pulse">
        <div className="h-6 w-48 rounded" style={{ background: colors.bg.glass }} />
        <div className="h-64 mt-4 rounded" style={{ background: colors.bg.glass }} />
      </GlassCard>
    );
  }

  return (
    <GlassCard>
      <CardHeader
        title="Movement Efficiency"
        subtitle="Energy output per distance traveled"
        rightContent={
          <CardTimeSelector value={timeRange} onChange={setTimeRange} compact />
        }
      />

      {data.length === 0 ? (
        <div
          className="h-64 flex items-center justify-center"
          style={{ color: colors.ui.text.muted }}
        >
          Not enough data to calculate efficiency
        </div>
      ) : (
        <>
          <ResponsiveContainer width="100%" height={260}>
            <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={colors.ui.border} />

              <ReferenceLine
                segment={[{ x: 0, y: 0 }, { x: 15, y: 750 }]}
                stroke={colors.state.good}
                strokeDasharray="4 4"
                strokeOpacity={0.3}
              />

              <XAxis
                type="number"
                dataKey="distance"
                name="Distance"
                domain={[0, 'auto']}
                tick={{ fill: colors.ui.text.muted, fontSize: 10 }}
                tickLine={false}
                axisLine={{ stroke: colors.ui.border }}
                label={{ value: 'Distance (km) →', position: 'bottom', offset: 0, fill: colors.ui.text.muted, fontSize: 10 }}
              />

              <YAxis
                type="number"
                dataKey="energy"
                name="Energy"
                domain={[0, 'auto']}
                tick={{ fill: colors.ui.text.muted, fontSize: 10 }}
                tickLine={false}
                axisLine={{ stroke: colors.ui.border }}
                label={{ value: 'Energy (kcal) →', angle: -90, position: 'left', offset: 10, fill: colors.ui.text.muted, fontSize: 10 }}
              />

              <Tooltip content={<CustomTooltip />} />

              <Scatter data={data}>
                {data.map((entry, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={getEfficiencyColor(entry.efficiency)}
                    fillOpacity={entry.isToday ? 1 : 0.6}
                    stroke={entry.isToday ? colors.ui.text.primary : 'none'}
                    strokeWidth={entry.isToday ? 2 : 0}
                    r={entry.isToday ? 10 : 5}
                    style={{
                      filter: entry.isToday ? `drop-shadow(0 0 8px ${getEfficiencyColor(entry.efficiency)})` : 'none',
                      cursor: 'pointer',
                    }}
                  />
                ))}
              </Scatter>
            </ScatterChart>
          </ResponsiveContainer>

          {stats && (
            <div 
              className="flex justify-center gap-4 mt-4"
            >
              <InsightBadge
                text={`Avg efficiency: ${(stats.avgEfficiency * 100).toFixed(0)}%`}
                variant={stats.avgEfficiency >= 1 ? 'good' : 'neutral'}
              />
              {stats.highEffDays > 0 && (
                <InsightBadge
                  text={`${stats.highEffDays} high-intensity days`}
                  variant="good"
                />
              )}
            </div>
          )}

          {todayPoint && (
            <div 
              className="flex justify-center gap-6 mt-4 pt-4"
              style={{ borderTop: `1px solid ${colors.ui.border}` }}
            >
              <div className="text-center">
                <span className="text-xs" style={{ color: colors.ui.text.muted }}>Today's Efficiency</span>
                <p 
                  className="text-2xl font-bold"
                  style={{ color: getEfficiencyColor(todayPoint.efficiency) }}
                >
                  {(todayPoint.efficiency * 100).toFixed(0)}%
                </p>
              </div>
            </div>
          )}
        </>
      )}

      <TeachingLine
        text="Higher energy per distance means more intense movement. Points above the line indicate high-effort days."
        direction="higher"
      />
    </GlassCard>
  );
}
