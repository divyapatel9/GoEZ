/**
 * Recovery Score Hero Card - Premium Redesign
 */

import { useState, useEffect, useMemo, useCallback } from 'react';
import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts';
import { GlassCard, CardHeader, TeachingLine, CardTimeSelector, getDateRangeFromPreset } from '@/shared/ui';
import type { TimeRange } from '@/shared/ui';
import { colors, getRecoveryStyles } from '@/styles/theme';
import type { DailyScore } from '@/types/insights';
import { getScores } from '@/services/insights_api';
import { useSelectedDate } from '@/context';

interface RecoveryGaugeProps {
  initialRange?: TimeRange;
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function generateTeachingLine(score: DailyScore | null): string {
  if (!score || score.recovery_score === null) {
    return "Recovery data not available for this day.";
  }

  const { contributors, recovery_score, recovery_label } = score;
  const parts: string[] = [];

  if (contributors.hrv_pct !== null) {
    if (contributors.hrv_pct < -20) {
      parts.push("HRV dropped below baseline");
    } else if (contributors.hrv_pct > 20) {
      parts.push("HRV is elevated above baseline");
    }
  }

  if (contributors.rhr_pct !== null) {
    if (contributors.rhr_pct < -20) {
      parts.push("resting heart rate is higher than usual");
    } else if (contributors.rhr_pct > 20) {
      parts.push("resting heart rate is lower than usual");
    }
  }

  if (contributors.effort_pct !== null) {
    if (contributors.effort_pct < -20) {
      parts.push("yesterday's effort was high");
    } else if (contributors.effort_pct > 20) {
      parts.push("yesterday was a light day");
    }
  }

  if (parts.length === 0) {
    if (recovery_score >= 67) {
      return "Your body is well-recovered and ready for activity.";
    } else if (recovery_score >= 34) {
      return "Recovery is moderate. Listen to your body today.";
    }
    return "Focus on rest and recovery today.";
  }

  const reason = parts.join(" and ");
  return `Recovery is ${recovery_label?.toLowerCase() || 'moderate'} because ${reason}.`;
}

function ContributorBar({ 
  label, 
  value, 
  icon 
}: { 
  label: string; 
  value: number | null;
  icon: string;
}) {
  if (value === null) return null;

  const impact = Math.round(value * 0.5);
  const isPositive = impact >= 0;
  const absValue = Math.abs(impact);
  const maxWidth = 100;
  const barWidth = Math.min(absValue * 2, maxWidth);

  return (
    <div className="flex items-center gap-3 mb-3">
      <span className="text-lg w-6">{icon}</span>
      <span 
        className="w-28 text-sm"
        style={{ color: colors.ui.text.secondary }}
      >
        {label}
      </span>
      
      <div className="flex-1 flex items-center gap-2">
        <div 
          className="flex-1 h-2 rounded-full overflow-hidden relative"
          style={{ background: colors.bg.glass }}
        >
          <div className="absolute inset-0 flex items-center justify-center">
            <div 
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${barWidth}%`,
                marginLeft: isPositive ? '50%' : `${50 - barWidth}%`,
                marginRight: isPositive ? 'auto' : '50%',
                background: isPositive ? colors.state.good : colors.state.danger,
                boxShadow: isPositive 
                  ? `0 0 10px ${colors.recovery.ready.glow}`
                  : `0 0 10px ${colors.recovery.recover.glow}`,
              }}
            />
          </div>
          <div 
            className="absolute top-0 bottom-0 w-px"
            style={{ 
              left: '50%',
              background: colors.ui.border,
            }}
          />
        </div>
        
        <span 
          className="w-12 text-sm font-semibold text-right"
          style={{ color: isPositive ? colors.state.good : colors.state.danger }}
        >
          {isPositive ? '+' : ''}{impact}
        </span>
      </div>
    </div>
  );
}

function DayPill({ 
  score, 
  isSelected, 
  onClick 
}: { 
  score: DailyScore; 
  isSelected: boolean;
  onClick: () => void;
}) {
  const styles = getRecoveryStyles(score.recovery_score);
  const dayLabel = new Date(score.date).toLocaleDateString('en-US', { weekday: 'short' });

  return (
    <button
      onClick={onClick}
      className="flex flex-col items-center gap-1 transition-all duration-200"
      style={{
        opacity: isSelected ? 1 : 0.6,
        transform: isSelected ? 'scale(1.1)' : 'scale(1)',
      }}
    >
      <div
        className="w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold transition-all"
        style={{
          background: score.recovery_score !== null 
            ? styles.gradient 
            : colors.state.missing,
          color: score.recovery_score !== null ? '#000' : colors.ui.text.muted,
          boxShadow: isSelected ? styles.shadow : 'none',
          border: isSelected ? `2px solid ${colors.ui.text.primary}` : 'none',
        }}
      >
        {score.recovery_score ?? '—'}
      </div>
      <span 
        className="text-xs"
        style={{ color: isSelected ? colors.ui.text.primary : colors.ui.text.muted }}
      >
        {dayLabel}
      </span>
    </button>
  );
}

function RecoveryRibbon({ scores }: { scores: DailyScore[] }) {
  if (scores.length < 2) return null;

  return (
    <div className="flex items-center gap-0.5 mb-6">
      {scores.map((s, i) => {
        const styles = getRecoveryStyles(s.recovery_score);
        return (
          <div
            key={s.date}
            className="flex-1 h-1.5 rounded-full transition-all"
            style={{
              background: s.recovery_score !== null ? styles.color : colors.state.missing,
              opacity: 0.3 + (i / scores.length) * 0.7,
            }}
          />
        );
      })}
    </div>
  );
}

export function RecoveryGauge({ initialRange = '7d' }: RecoveryGaugeProps) {
  const [timeRange, setTimeRange] = useState<TimeRange>(initialRange);
  const [scores, setScores] = useState<DailyScore[]>([]);
  const [selectedIndex, setSelectedIndex] = useState<number>(-1);
  const [isLoading, setIsLoading] = useState(true);
  const [animatedScore, setAnimatedScore] = useState(0);
  const { setSelectedDate } = useSelectedDate();

  const handleDaySelect = useCallback((date: string) => {
    const globalIndex = scores.findIndex(sc => sc.date === date);
    if (globalIndex >= 0) {
      setSelectedIndex(globalIndex);
      setSelectedDate(date, 'recovery-gauge');
    }
  }, [scores, setSelectedDate]);

  useEffect(() => {
    async function loadData() {
      setIsLoading(true);
      try {
        const { start, end } = getDateRangeFromPreset(timeRange);
        const response = await getScores(start, end);
        setScores(response.scores);
        setSelectedIndex(response.scores.length - 1);
      } catch (err) {
        console.error('Failed to load scores:', err);
      } finally {
        setIsLoading(false);
      }
    }
    loadData();
  }, [timeRange]);

  const selectedScore = scores[selectedIndex] || null;
  const targetScore = selectedScore?.recovery_score ?? 0;

  useEffect(() => {
    if (targetScore === 0) {
      setAnimatedScore(0);
      return;
    }

    const duration = 800;
    const steps = 30;
    const increment = targetScore / steps;
    let current = 0;
    
    const timer = setInterval(() => {
      current += increment;
      if (current >= targetScore) {
        setAnimatedScore(targetScore);
        clearInterval(timer);
      } else {
        setAnimatedScore(Math.round(current));
      }
    }, duration / steps);

    return () => clearInterval(timer);
  }, [targetScore, selectedIndex]);

  const styles = getRecoveryStyles(selectedScore?.recovery_score ?? null);
  const gaugeData = [
    { value: animatedScore },
    { value: 100 - animatedScore },
  ];

  const teachingLine = useMemo(
    () => generateTeachingLine(selectedScore),
    [selectedScore]
  );

  const displayDays = timeRange === '1d' ? scores.slice(-1) : scores.slice(-7);
  const recoveryScore = selectedScore?.recovery_score ?? null;
  const glowColor =
    recoveryScore === null
      ? 'none'
      : recoveryScore >= 67
        ? 'green'
        : recoveryScore >= 34
          ? 'yellow'
          : 'red';

  if (isLoading) {
    return (
      <GlassCard className="animate-pulse">
        <div className="h-6 w-32 rounded" style={{ background: colors.bg.glass }} />
        <div className="h-64 mt-4 rounded-full mx-auto w-48" style={{ background: colors.bg.glass }} />
      </GlassCard>
    );
  }

  return (
    <GlassCard glow={glowColor as 'green' | 'yellow' | 'red' | 'none'}>
      <CardHeader
        title="Recovery"
        subtitle="How ready you are compared to your baseline"
        rightContent={
          <CardTimeSelector value={timeRange} onChange={setTimeRange} compact />
        }
      />

      <RecoveryRibbon scores={scores} />

      <div className="flex items-center justify-center">
        <div className="relative w-56 h-56">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <defs>
                <linearGradient id="gaugeGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor={colors.recovery.recover.primary} />
                  <stop offset="50%" stopColor={colors.recovery.caution.primary} />
                  <stop offset="100%" stopColor={colors.recovery.ready.primary} />
                </linearGradient>
              </defs>
              <Pie
                data={gaugeData}
                cx="50%"
                cy="50%"
                startAngle={180}
                endAngle={0}
                innerRadius={70}
                outerRadius={90}
                paddingAngle={0}
                dataKey="value"
              >
                <Cell fill={styles.color} />
                <Cell fill={colors.bg.glass} />
              </Pie>
            </PieChart>
          </ResponsiveContainer>

          <div 
            className="absolute inset-0 flex flex-col items-center justify-center"
            style={{ filter: `drop-shadow(${styles.shadow})` }}
          >
            <span
              className="text-6xl font-bold tabular-nums"
              style={{ color: styles.color }}
            >
              {selectedScore?.recovery_score ?? '—'}
            </span>
            <span
              className="text-sm font-medium mt-1"
              style={{ color: colors.ui.text.secondary }}
            >
              {selectedScore?.recovery_label || 'No data'}
            </span>
            <span
              className="text-xs mt-2 px-2 py-0.5 rounded-full"
              style={{ 
                background: colors.bg.glass,
                color: colors.ui.text.muted 
              }}
            >
              {selectedScore ? formatDate(selectedScore.date) : '—'}
            </span>
          </div>
        </div>
      </div>

      {displayDays.length > 1 && (
        <div className="flex justify-center gap-2 mt-6">
          {displayDays.map((s) => (
            <DayPill
              key={s.date}
              score={s}
              isSelected={scores[selectedIndex]?.date === s.date}
              onClick={() => handleDaySelect(s.date)}
            />
          ))}
        </div>
      )}

      <div className="mt-6 pt-4" style={{ borderTop: `1px solid ${colors.ui.border}` }}>
        <h4 
          className="text-sm font-medium mb-4"
          style={{ color: colors.ui.text.secondary }}
        >
          Contributors
        </h4>
        <ContributorBar
          label="HRV"
          value={selectedScore?.contributors.hrv_pct ?? null}
          icon="💓"
        />
        <ContributorBar
          label="Resting HR"
          value={selectedScore?.contributors.rhr_pct ?? null}
          icon="❤️"
        />
        <ContributorBar
          label="Yesterday's Effort"
          value={selectedScore?.contributors.effort_pct ?? null}
          icon="🔥"
        />
      </div>

      <TeachingLine text={teachingLine} direction="higher" />
    </GlassCard>
  );
}
