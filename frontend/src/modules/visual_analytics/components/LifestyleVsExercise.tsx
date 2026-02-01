/**
 * Lifestyle vs Exercise Card - New Insight
 * 
 * Compares Steps + Exercise Time + Stand Hours
 * Visual: Split donut or stacked bar showing workout vs daily movement
 * Teaching: "Shows whether movement came from workouts or daily life."
 */

import { useState, useEffect, useMemo } from 'react';
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import { GlassCard, CardHeader, TeachingLine, InsightBadge, CardTimeSelector, getDateRangeFromPreset } from '@/shared/ui';
import type { TimeRange } from '@/shared/ui';
import { colors } from '@/styles/theme';
import { getDailyMetric } from '@/services/analytics_api';

interface LifestyleVsExerciseProps {
  initialRange?: TimeRange;
}

interface ActivityData {
  date: string;
  steps: number;
  exerciseTime: number;
  standHours: number;
}

const ACTIVITY_COLORS = {
  exercise: '#10b981',
  lifestyle: '#3b82f6',
  standing: '#8b5cf6',
};

function CustomTooltip({ active, payload }: any) {
  if (!active || !payload || !payload.length) return null;

  const { name, value, payload: data } = payload[0];

  return (
    <div
      className="px-4 py-3 rounded-xl"
      style={{
        background: colors.bg.card,
        border: `1px solid ${colors.ui.border}`,
        boxShadow: '0 4px 20px rgba(0,0,0,0.5)',
      }}
    >
      <div className="flex items-center gap-2 mb-1">
        <div
          className="w-3 h-3 rounded"
          style={{ background: data.fill }}
        />
        <span className="font-semibold" style={{ color: colors.ui.text.primary }}>
          {name}
        </span>
      </div>
      <p className="text-lg font-bold" style={{ color: data.fill }}>
        {value.toFixed(0)}%
      </p>
    </div>
  );
}

export function LifestyleVsExercise({ initialRange = '30d' }: LifestyleVsExerciseProps) {
  const [timeRange, setTimeRange] = useState<TimeRange>(initialRange);
  const [data, setData] = useState<ActivityData[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      setIsLoading(true);
      try {
        const { start, end } = getDateRangeFromPreset(timeRange);
        const [stepsRes, exerciseRes, standRes] = await Promise.all([
          getDailyMetric('steps', start, end),
          getDailyMetric('exercise_time', start, end),
          getDailyMetric('stand_hours', start, end),
        ]);

        const stepsMap = new Map(stepsRes.data.map(d => [d.date, d.value || 0]));
        const exerciseMap = new Map(exerciseRes.data.map(d => [d.date, d.value || 0]));
        const standMap = new Map(standRes.data.map(d => [d.date, d.value || 0]));

        const allDates = [...new Set([
          ...stepsRes.data.map(d => d.date),
          ...exerciseRes.data.map(d => d.date),
        ])].sort();

        const activityData: ActivityData[] = allDates.map(date => ({
          date,
          steps: stepsMap.get(date) || 0,
          exerciseTime: exerciseMap.get(date) || 0,
          standHours: standMap.get(date) || 0,
        }));

        setData(activityData);
      } catch (err) {
        console.error('Failed to load activity data:', err);
      } finally {
        setIsLoading(false);
      }
    }
    loadData();
  }, [timeRange]);

  const totals = useMemo(() => {
    return data.reduce((acc, d) => ({
      steps: acc.steps + d.steps,
      exerciseTime: acc.exerciseTime + d.exerciseTime,
      standHours: acc.standHours + d.standHours,
    }), { steps: 0, exerciseTime: 0, standHours: 0 });
  }, [data]);

  const pieData = useMemo(() => {
    const exercisePoints = totals.exerciseTime * 10;
    const lifestylePoints = totals.steps / 100;
    const standingPoints = totals.standHours * 5;
    const total = exercisePoints + lifestylePoints + standingPoints;

    if (total === 0) return [];

    return [
      { name: 'Exercise', value: (exercisePoints / total) * 100, fill: ACTIVITY_COLORS.exercise, raw: totals.exerciseTime },
      { name: 'Daily Movement', value: (lifestylePoints / total) * 100, fill: ACTIVITY_COLORS.lifestyle, raw: totals.steps },
      { name: 'Standing', value: (standingPoints / total) * 100, fill: ACTIVITY_COLORS.standing, raw: totals.standHours },
    ];
  }, [totals]);

  const dominantActivity = useMemo(() => {
    if (pieData.length === 0) return null;
    return pieData.reduce((max, d) => d.value > max.value ? d : max);
  }, [pieData]);

  const insight = useMemo(() => {
    if (!dominantActivity) return null;
    
    if (dominantActivity.name === 'Exercise') {
      return { text: 'Most activity from dedicated workouts', variant: 'good' as const };
    } else if (dominantActivity.name === 'Daily Movement') {
      return { text: 'Most activity from daily movement', variant: 'neutral' as const };
    } else {
      return { text: 'Standing contributes significantly', variant: 'neutral' as const };
    }
  }, [dominantActivity]);

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
        title="Lifestyle vs Exercise"
        subtitle="Where your movement came from"
        rightContent={
          <CardTimeSelector value={timeRange} onChange={setTimeRange} compact />
        }
      />

      {pieData.length === 0 ? (
        <div
          className="h-64 flex items-center justify-center"
          style={{ color: colors.ui.text.muted }}
        >
          No activity data available
        </div>
      ) : (
        <>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <defs>
                {Object.entries(ACTIVITY_COLORS).map(([key, color]) => (
                  <linearGradient key={key} id={`grad-${key}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={color} stopOpacity={1} />
                    <stop offset="100%" stopColor={color} stopOpacity={0.6} />
                  </linearGradient>
                ))}
                <filter id="donutGlow">
                  <feGaussianBlur stdDeviation="3" result="coloredBlur" />
                  <feMerge>
                    <feMergeNode in="coloredBlur" />
                    <feMergeNode in="SourceGraphic" />
                  </feMerge>
                </filter>
              </defs>

              <Pie
                data={pieData}
                cx="50%"
                cy="50%"
                innerRadius={60}
                outerRadius={90}
                paddingAngle={2}
                dataKey="value"
                filter="url(#donutGlow)"
              >
                {pieData.map((entry, index) => (
                  <Cell 
                    key={`cell-${index}`} 
                    fill={entry.fill}
                    style={{ filter: `drop-shadow(0 0 8px ${entry.fill}40)` }}
                  />
                ))}
              </Pie>

              <Tooltip content={<CustomTooltip />} />
            </PieChart>
          </ResponsiveContainer>

          <div 
            className="flex justify-center gap-6 -mt-4"
          >
            {pieData.map((entry) => (
              <div key={entry.name} className="flex items-center gap-2">
                <div
                  className="w-3 h-3 rounded"
                  style={{ background: entry.fill }}
                />
                <span className="text-xs" style={{ color: colors.ui.text.secondary }}>
                  {entry.name} ({entry.value.toFixed(0)}%)
                </span>
              </div>
            ))}
          </div>

          {insight && (
            <div className="flex justify-center mt-4">
              <InsightBadge text={insight.text} variant={insight.variant} />
            </div>
          )}

          <div 
            className="grid grid-cols-3 gap-4 mt-4 pt-4"
            style={{ borderTop: `1px solid ${colors.ui.border}` }}
          >
            <div className="text-center">
              <span className="text-lg">💪</span>
              <p className="text-xs" style={{ color: colors.ui.text.muted }}>Exercise</p>
              <p className="font-semibold text-sm" style={{ color: ACTIVITY_COLORS.exercise }}>
                {totals.exerciseTime.toFixed(0)} min
              </p>
            </div>
            <div className="text-center">
              <span className="text-lg">👟</span>
              <p className="text-xs" style={{ color: colors.ui.text.muted }}>Steps</p>
              <p className="font-semibold text-sm" style={{ color: ACTIVITY_COLORS.lifestyle }}>
                {(totals.steps / 1000).toFixed(1)}k
              </p>
            </div>
            <div className="text-center">
              <span className="text-lg">🧍</span>
              <p className="text-xs" style={{ color: colors.ui.text.muted }}>Stand Hours</p>
              <p className="font-semibold text-sm" style={{ color: ACTIVITY_COLORS.standing }}>
                {totals.standHours.toFixed(0)} hrs
              </p>
            </div>
          </div>
        </>
      )}

      <TeachingLine
        text="Shows whether your movement came from dedicated workouts or daily lifestyle activities."
        direction="balanced"
      />
    </GlassCard>
  );
}
