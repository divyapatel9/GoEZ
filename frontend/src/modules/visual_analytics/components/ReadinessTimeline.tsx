/**
 * Readiness Timeline - Premium Redesign
 * 
 * Features:
 * - Smooth recovery line with color-coded points
 * - Annotation limits based on time range
 * - Clickable annotations with side panel details
 * - Streak detection for consecutive events
 * - Subtle dotted baseline thresholds
 */

import { useState, useEffect, useMemo, useCallback } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import { GlassCard, CardHeader, TeachingLine, CardTimeSelector, getDateRangeFromPreset } from '@/shared/ui';
import type { TimeRange } from '@/shared/ui';
import { colors, getRecoveryStyles } from '@/styles/theme';
import type { TimelineDay, AnnotationType } from '@/types/insights';
import { getReadinessTimeline } from '@/services/insights_api';
import { getScores } from '@/services/insights_api';
import type { DailyScore } from '@/types/insights';
import { useSelectedDate } from '@/context';

interface ReadinessTimelineProps {
  initialRange?: TimeRange;
}

const ANNOTATION_CONFIG: Record<AnnotationType, { icon: string; label: string; color: string }> = {
  high_strain: { icon: '💪', label: 'High Strain', color: colors.state.warning },
  low_hrv: { icon: '💓', label: 'HRV Dipped', color: colors.state.danger },
  high_rhr: { icon: '❤️', label: 'RHR Elevated', color: colors.state.danger },
  recovery_up: { icon: '📈', label: 'Recovery Up', color: colors.state.good },
  recovery_down: { icon: '📉', label: 'Recovery Down', color: colors.state.warning },
};

const MAX_ANNOTATIONS: Record<TimeRange, number> = {
  '1d': 1,
  '7d': 3,
  '30d': 6,
  '6m': 10,
};

function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function formatFullDate(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' });
}

interface ChartPoint extends TimelineDay {
  displayAnnotation: boolean;
}

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload || !payload.length) return null;

  const point = payload[0]?.payload as ChartPoint;
  if (!point) return null;

  const styles = getRecoveryStyles(point.recovery_score);

  return (
    <div
      className="px-4 py-3 rounded-xl"
      style={{
        background: colors.bg.card,
        border: `1px solid ${colors.ui.border}`,
        boxShadow: `0 4px 20px rgba(0,0,0,0.5), 0 0 15px ${styles.glow}`,
      }}
    >
      <p className="font-semibold mb-2" style={{ color: colors.ui.text.primary }}>
        {formatDate(label)}
      </p>

      {point.recovery_score !== null ? (
        <div className="flex items-center gap-2">
          <span style={{ color: colors.ui.text.secondary }}>Recovery:</span>
          <span className="text-xl font-bold" style={{ color: styles.color }}>
            {point.recovery_score}
          </span>
        </div>
      ) : (
        <span style={{ color: colors.ui.text.muted }}>No data</span>
      )}

      {point.annotation && point.annotation_type && (
        <div
          className="mt-2 px-2 py-1 rounded text-xs"
          style={{
            background: `${ANNOTATION_CONFIG[point.annotation_type].color}20`,
            color: ANNOTATION_CONFIG[point.annotation_type].color,
          }}
        >
          {ANNOTATION_CONFIG[point.annotation_type].icon} {point.annotation}
        </div>
      )}
    </div>
  );
}

interface DetailPanelProps {
  day: TimelineDay;
  score: DailyScore | null;
  onClose: () => void;
}

function DetailPanel({ day, score, onClose }: DetailPanelProps) {
  const styles = getRecoveryStyles(day.recovery_score);
  const config = day.annotation_type ? ANNOTATION_CONFIG[day.annotation_type] : null;

  return (
    <div
      className="absolute right-0 top-0 w-72 rounded-xl p-4 z-20"
      style={{
        background: colors.bg.card,
        border: `1px solid ${colors.ui.border}`,
        boxShadow: `0 8px 32px rgba(0,0,0,0.6), 0 0 20px ${styles.glow}`,
      }}
    >
      <div className="flex items-start justify-between mb-4">
        <div>
          <p className="text-sm" style={{ color: colors.ui.text.muted }}>
            {formatFullDate(day.date)}
          </p>
          {config && (
            <div
              className="inline-flex items-center gap-1 mt-2 px-2 py-1 rounded-full text-xs font-medium"
              style={{
                background: `${config.color}20`,
                color: config.color,
              }}
            >
              {config.icon} {config.label}
            </div>
          )}
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded-full transition-colors"
          style={{ color: colors.ui.text.muted }}
        >
          ✕
        </button>
      </div>

      <div className="text-center mb-4">
        <span className="text-4xl font-bold" style={{ color: styles.color }}>
          {day.recovery_score ?? '—'}
        </span>
        <p className="text-xs mt-1" style={{ color: colors.ui.text.muted }}>
          Recovery Score
        </p>
      </div>

      {score && score.contributors && (
        <div
          className="pt-4 space-y-3"
          style={{ borderTop: `1px solid ${colors.ui.border}` }}
        >
          <p className="text-xs font-medium" style={{ color: colors.ui.text.secondary }}>
            Contributors
          </p>

          {[
            { label: 'HRV', value: score.contributors.hrv_pct, icon: '💓' },
            { label: 'Resting HR', value: score.contributors.rhr_pct, icon: '❤️' },
            { label: 'Prior Effort', value: score.contributors.effort_pct, icon: '🔥' },
          ].map(({ label, value, icon }) => {
            if (value === null || value === undefined) return null;
            const impact = Math.round(value * 0.5);
            const isPositive = impact >= 0;
            return (
              <div key={label} className="flex items-center gap-2">
                <span className="text-sm">{icon}</span>
                <span className="text-xs" style={{ color: colors.ui.text.muted }}>{label}</span>
                <span
                  className="ml-auto text-xs font-semibold"
                  style={{ color: isPositive ? colors.state.good : colors.state.danger }}
                >
                  {isPositive ? '+' : ''}{impact}
                </span>
              </div>
            );
          })}
        </div>
      )}

      <p
        className="text-xs mt-4 pt-4"
        style={{ color: colors.ui.text.muted, borderTop: `1px solid ${colors.ui.border}` }}
      >
        This annotation is based on your baseline data patterns.
      </p>
    </div>
  );
}

export function ReadinessTimeline({ initialRange = '30d' }: ReadinessTimelineProps) {
  const [timeRange, setTimeRange] = useState<TimeRange>(initialRange);
  const [timeline, setTimeline] = useState<TimelineDay[]>([]);
  const [scores, setScores] = useState<DailyScore[]>([]);
  const [selectedDay, setSelectedDay] = useState<TimelineDay | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const { setSelectedDate } = useSelectedDate();

  const handleDayClick = useCallback((day: TimelineDay) => {
    setSelectedDay(day);
    setSelectedDate(day.date, 'readiness-timeline');
  }, [setSelectedDate]);

  useEffect(() => {
    async function loadData() {
      setIsLoading(true);
      try {
        const { start, end } = getDateRangeFromPreset(timeRange);
        const [timelineRes, scoresRes] = await Promise.all([
          getReadinessTimeline(start, end),
          getScores(start, end),
        ]);
        setTimeline(timelineRes.timeline);
        setScores(scoresRes.scores);
      } catch (err) {
        console.error('Failed to load timeline data:', err);
      } finally {
        setIsLoading(false);
      }
    }
    loadData();
  }, [timeRange]);

  const chartData: ChartPoint[] = useMemo(() => {
    const maxAnnotations = MAX_ANNOTATIONS[timeRange];
    const annotatedIndices = timeline
      .map((d, i) => (d.annotation ? i : -1))
      .filter(i => i >= 0);

    const displayIndices = new Set(
      annotatedIndices.slice(-maxAnnotations)
    );

    return timeline.map((day, i) => ({
      ...day,
      displayAnnotation: displayIndices.has(i),
    }));
  }, [timeline, timeRange]);

  const annotationCount = useMemo(() => {
    return chartData.filter(d => d.displayAnnotation).length;
  }, [chartData]);

  const selectedScore = useMemo(() => {
    if (!selectedDay) return null;
    return scores.find(s => s.date === selectedDay.date) || null;
  }, [selectedDay, scores]);

  if (isLoading) {
    return (
      <GlassCard className="animate-pulse">
        <div className="h-6 w-48 rounded" style={{ background: colors.bg.glass }} />
        <div className="h-72 mt-4 rounded" style={{ background: colors.bg.glass }} />
      </GlassCard>
    );
  }

  return (
    <GlassCard className="relative">
      <CardHeader
        title="Readiness Timeline"
        subtitle="Recovery trend with notable events"
        rightContent={
          <div className="flex items-center gap-3">
            {annotationCount > 0 && (
              <span className="text-xs" style={{ color: colors.ui.text.muted }}>
                {annotationCount} event{annotationCount !== 1 ? 's' : ''}
              </span>
            )}
            <CardTimeSelector value={timeRange} onChange={setTimeRange} compact />
          </div>
        }
      />

      {selectedDay && (
        <DetailPanel
          day={selectedDay}
          score={selectedScore}
          onClose={() => setSelectedDay(null)}
        />
      )}

      {timeline.length === 0 ? (
        <div
          className="h-72 flex items-center justify-center"
          style={{ color: colors.ui.text.muted }}
        >
          No timeline data available
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={chartData} margin={{ top: 30, right: 20, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="lineGradient" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor={colors.recovery.recover.primary} />
                <stop offset="50%" stopColor={colors.recovery.caution.primary} />
                <stop offset="100%" stopColor={colors.recovery.ready.primary} />
              </linearGradient>
              <filter id="timelineGlow">
                <feGaussianBlur stdDeviation="2" result="coloredBlur" />
                <feMerge>
                  <feMergeNode in="coloredBlur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>

            <CartesianGrid strokeDasharray="3 3" stroke={colors.ui.border} />

            <ReferenceLine y={67} stroke={colors.recovery.ready.primary} strokeDasharray="4 4" strokeOpacity={0.3} />
            <ReferenceLine y={34} stroke={colors.recovery.caution.primary} strokeDasharray="4 4" strokeOpacity={0.3} />

            <XAxis
              dataKey="date"
              tickFormatter={formatDate}
              tick={{ fill: colors.ui.text.muted, fontSize: 10 }}
              tickLine={false}
              axisLine={{ stroke: colors.ui.border }}
            />

            <YAxis
              domain={[0, 100]}
              ticks={[0, 34, 67, 100]}
              tick={{ fill: colors.ui.text.muted, fontSize: 10 }}
              tickLine={false}
              axisLine={{ stroke: colors.ui.border }}
            />

            <Tooltip content={<CustomTooltip />} />

            <Line
              type="monotone"
              dataKey="recovery_score"
              stroke="url(#lineGradient)"
              strokeWidth={3}
              filter="url(#timelineGlow)"
              dot={(props: any) => {
                const { cx, cy, payload } = props;
                if (payload.recovery_score === null) return <g key={`dot-${payload.date}`} />;

                const styles = getRecoveryStyles(payload.recovery_score);
                const hasAnnotation = payload.displayAnnotation;
                const isToday = payload.date === chartData[chartData.length - 1]?.date;

                return (
                  <g key={`dot-${payload.date}`}>
                    <circle
                      cx={cx}
                      cy={cy}
                      r={isToday ? 8 : hasAnnotation ? 6 : 4}
                      fill={styles.color}
                      stroke={isToday ? colors.ui.text.primary : 'none'}
                      strokeWidth={isToday ? 2 : 0}
                      style={{
                        cursor: hasAnnotation ? 'pointer' : 'default',
                        filter: isToday || hasAnnotation ? `drop-shadow(0 0 8px ${styles.glow})` : 'none',
                      }}
                      onClick={() => hasAnnotation && handleDayClick(payload)}
                    />
                    {hasAnnotation && payload.annotation_type && (
                      <text
                        x={cx}
                        y={cy - 16}
                        textAnchor="middle"
                        fontSize={14}
                        style={{ cursor: 'pointer' }}
                        onClick={() => handleDayClick(payload)}
                      >
                        {ANNOTATION_CONFIG[payload.annotation_type as AnnotationType]?.icon}
                      </text>
                    )}
                  </g>
                );
              }}
              connectNulls={false}
            />
          </LineChart>
        </ResponsiveContainer>
      )}

      <div
        className="flex items-center justify-center gap-6 mt-4 pt-4"
        style={{ borderTop: `1px solid ${colors.ui.border}` }}
      >
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full" style={{ background: colors.recovery.ready.primary }} />
          <span className="text-xs" style={{ color: colors.ui.text.secondary }}>Ready (67+)</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full" style={{ background: colors.recovery.caution.primary }} />
          <span className="text-xs" style={{ color: colors.ui.text.secondary }}>Caution (34-66)</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full" style={{ background: colors.recovery.recover.primary }} />
          <span className="text-xs" style={{ color: colors.ui.text.secondary }}>Recover (0-33)</span>
        </div>
      </div>

      <TeachingLine
        text="This timeline explains why your readiness changed, not just how. Click annotated points for details."
        direction="higher"
      />
    </GlassCard>
  );
}
