/**
 * Recovery vs Strain Quadrant - Premium Redesign
 */

import { useState, useEffect, useMemo, useCallback } from 'react';
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
  Label,
} from 'recharts';
import { GlassCard, CardHeader, TeachingLine, InsightBadge, CardTimeSelector, getDateRangeFromPreset } from '@/shared/ui';
import type { TimeRange } from '@/shared/ui';
import { colors, getRecoveryStyles } from '@/styles/theme';
import type { RecoveryStrainPoint } from '@/types/insights';
import { getRecoveryVsStrain } from '@/services/insights_api';
import { useSelectedDate } from '@/context';

interface RecoveryStrainQuadrantProps {
  initialRange?: TimeRange;
}

interface ChartPoint extends RecoveryStrainPoint {
  isToday: boolean;
  size: number;
}

const QUADRANT_LABELS = [
  { x: 75, y: 85, label: 'Peak Performance', emoji: '🚀' },
  { x: 75, y: 15, label: 'Overreaching', emoji: '⚠️' },
  { x: 25, y: 85, label: 'Undertraining', emoji: '😴' },
  { x: 25, y: 15, label: 'Low Readiness', emoji: '🔋' },
];

function getQuadrant(recovery: number, strain: number): string {
  if (recovery >= 50 && strain >= 50) return 'peak';
  if (recovery < 50 && strain >= 50) return 'overreaching';
  if (recovery >= 50 && strain < 50) return 'undertraining';
  return 'low_readiness';
}

function CustomTooltip({ active, payload }: any) {
  if (!active || !payload || !payload.length) return null;

  const point = payload[0].payload as ChartPoint;
  const styles = getRecoveryStyles(point.recovery_score);
  const date = new Date(point.date).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });

  return (
    <div
      className="px-4 py-3 rounded-xl"
      style={{
        background: colors.bg.card,
        border: `1px solid ${colors.ui.border}`,
        boxShadow: `0 4px 20px rgba(0,0,0,0.5), 0 0 20px ${styles.glow}`,
      }}
    >
      <p
        className="font-semibold mb-2"
        style={{ color: colors.ui.text.primary }}
      >
        {point.isToday ? '📍 Today' : date}
      </p>
      <div className="flex items-center gap-4">
        <div>
          <span className="text-xs" style={{ color: colors.ui.text.muted }}>Recovery</span>
          <p className="text-lg font-bold" style={{ color: styles.color }}>
            {point.recovery_score}
          </p>
        </div>
        <div>
          <span className="text-xs" style={{ color: colors.ui.text.muted }}>Strain</span>
          <p className="text-lg font-bold" style={{ color: colors.metrics.strain }}>
            {point.strain_score}
          </p>
        </div>
      </div>
    </div>
  );
}

export function RecoveryStrainQuadrant({ initialRange = '30d' }: RecoveryStrainQuadrantProps) {
  const [timeRange, setTimeRange] = useState<TimeRange>(initialRange);
  const [points, setPoints] = useState<RecoveryStrainPoint[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const { setSelectedDate } = useSelectedDate();

  const handlePointClick = useCallback((date: string) => {
    setSelectedDate(date, 'recovery-strain-quadrant');
  }, [setSelectedDate]);

  useEffect(() => {
    async function loadData() {
      setIsLoading(true);
      try {
        const { start, end } = getDateRangeFromPreset(timeRange);
        const response = await getRecoveryVsStrain(start, end);
        setPoints(response.points);
      } catch (err) {
        console.error('Failed to load quadrant data:', err);
      } finally {
        setIsLoading(false);
      }
    }
    loadData();
  }, [timeRange]);

  const chartData: ChartPoint[] = useMemo(() => {
    return points.map((p, i) => ({
      ...p,
      isToday: i === points.length - 1,
      size: 40 + (p.strain_score / 100) * 60,
    }));
  }, [points]);

  const todayPoint = chartData.find(p => p.isToday);

  const zoneStats = useMemo(() => {
    const stats = { peak: 0, overreaching: 0, undertraining: 0, low_readiness: 0 };
    points.forEach(p => {
      const q = getQuadrant(p.recovery_score, p.strain_score);
      stats[q as keyof typeof stats]++;
    });
    return stats;
  }, [points]);

  const insightText = useMemo(() => {
    if (points.length === 0) return null;
    if (zoneStats.overreaching > points.length * 0.3) {
      return `${zoneStats.overreaching} days in overreaching zone — consider more recovery time`;
    }
    if (zoneStats.peak > points.length * 0.5) {
      return `${zoneStats.peak} days in peak performance — excellent balance`;
    }
    if (zoneStats.undertraining > points.length * 0.4) {
      return `${zoneStats.undertraining} days undertraining — room to push harder`;
    }
    return null;
  }, [points, zoneStats]);

  const insightVariant = useMemo(() => {
    if (zoneStats.overreaching > points.length * 0.3) return 'warning';
    if (zoneStats.peak > points.length * 0.5) return 'good';
    return 'neutral';
  }, [points, zoneStats]);

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
        title="Recovery vs Strain"
        subtitle="Does your effort match your recovery?"
        rightContent={
          <CardTimeSelector value={timeRange} onChange={setTimeRange} compact />
        }
      />

      {points.length === 0 ? (
        <div 
          className="h-72 flex items-center justify-center"
          style={{ color: colors.ui.text.muted }}
        >
          No data with both scores available
        </div>
      ) : (
        <>
          <ResponsiveContainer width="100%" height={300}>
            <ScatterChart margin={{ top: 30, right: 30, bottom: 30, left: 30 }}>
              <defs>
                <linearGradient id="gridGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor={colors.recovery.ready.primary} stopOpacity={0.05} />
                  <stop offset="100%" stopColor={colors.recovery.recover.primary} stopOpacity={0.05} />
                </linearGradient>
              </defs>

              <CartesianGrid
                strokeDasharray="3 3"
                stroke={colors.ui.border}
                fill="url(#gridGradient)"
              />

              <ReferenceLine x={50} stroke={colors.ui.border} strokeDasharray="4 4" />
              <ReferenceLine y={50} stroke={colors.ui.border} strokeDasharray="4 4" />

              <XAxis
                type="number"
                dataKey="strain_score"
                domain={[0, 100]}
                tick={{ fill: colors.ui.text.muted, fontSize: 11 }}
                tickLine={false}
                axisLine={{ stroke: colors.ui.border }}
              >
                <Label
                  value="Strain →"
                  position="bottom"
                  offset={10}
                  style={{ fill: colors.ui.text.muted, fontSize: 11 }}
                />
              </XAxis>

              <YAxis
                type="number"
                dataKey="recovery_score"
                domain={[0, 100]}
                tick={{ fill: colors.ui.text.muted, fontSize: 11 }}
                tickLine={false}
                axisLine={{ stroke: colors.ui.border }}
              >
                <Label
                  value="Recovery →"
                  angle={-90}
                  position="left"
                  offset={10}
                  style={{ fill: colors.ui.text.muted, fontSize: 11 }}
                />
              </YAxis>

              <Tooltip content={<CustomTooltip />} />

              <Scatter 
                data={chartData} 
                shape="circle"
                onClick={(data) => data?.date && handlePointClick(data.date)}
              >
                {chartData.map((entry, index) => {
                  const styles = getRecoveryStyles(entry.recovery_score);
                  return (
                    <Cell
                      key={`cell-${index}`}
                      fill={styles.color}
                      fillOpacity={entry.isToday ? 1 : 0.6}
                      stroke={entry.isToday ? colors.ui.text.primary : 'none'}
                      strokeWidth={entry.isToday ? 3 : 0}
                      r={entry.isToday ? 12 : 6 + (entry.strain_score / 100) * 4}
                      style={{
                        filter: entry.isToday ? `drop-shadow(0 0 12px ${styles.glow})` : 'none',
                        cursor: 'pointer',
                      }}
                    />
                  );
                })}
              </Scatter>
            </ScatterChart>
          </ResponsiveContainer>

          {insightText && (
            <div className="flex justify-center mt-4">
              <InsightBadge text={insightText} variant={insightVariant as 'good' | 'warning' | 'neutral'} />
            </div>
          )}

          {todayPoint && (
            <div 
              className="flex justify-center gap-6 mt-4 pt-4"
              style={{ borderTop: `1px solid ${colors.ui.border}` }}
            >
              <div className="text-center">
                <span className="text-xs" style={{ color: colors.ui.text.muted }}>Today's Recovery</span>
                <p 
                  className="text-2xl font-bold"
                  style={{ color: getRecoveryStyles(todayPoint.recovery_score).color }}
                >
                  {todayPoint.recovery_score}
                </p>
              </div>
              <div className="text-center">
                <span className="text-xs" style={{ color: colors.ui.text.muted }}>Today's Strain</span>
                <p 
                  className="text-2xl font-bold"
                  style={{ color: colors.metrics.strain }}
                >
                  {todayPoint.strain_score}
                </p>
              </div>
            </div>
          )}
        </>
      )}

      <TeachingLine
        text="Balanced days sit in the top-right. Bottom-right means pushing harder than you can recover from."
        direction="balanced"
      />
    </GlassCard>
  );
}
