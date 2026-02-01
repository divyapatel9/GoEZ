/**
 * Per-Card Time Selector
 * Each card has its own time control (1d, 7d, 30d, 6m)
 */

import { colors, animations } from '../../styles/theme';

export type TimeRange = '1d' | '7d' | '30d' | '6m';

interface CardTimeSelectorProps {
  value: TimeRange;
  onChange: (range: TimeRange) => void;
  compact?: boolean;
}

const RANGES: { key: TimeRange; label: string; days: number }[] = [
  { key: '1d', label: '1D', days: 1 },
  { key: '7d', label: '7D', days: 7 },
  { key: '30d', label: '30D', days: 30 },
  { key: '6m', label: '6M', days: 180 },
];

export function getDateRangeFromPreset(range: TimeRange): { start: string; end: string } {
  const preset = RANGES.find(r => r.key === range);
  const days = preset?.days ?? 30;
  
  const end = new Date();
  const start = new Date();
  start.setDate(end.getDate() - days);
  
  return {
    start: start.toISOString().split('T')[0],
    end: end.toISOString().split('T')[0],
  };
}

export function CardTimeSelector({ value, onChange, compact = false }: CardTimeSelectorProps) {
  return (
    <div 
      className="flex items-center rounded-lg p-0.5"
      style={{ 
        background: colors.bg.glass,
        border: `1px solid ${colors.ui.border}`,
      }}
    >
      {RANGES.map((range) => (
        <button
          key={range.key}
          onClick={() => onChange(range.key)}
          className={`
            ${compact ? 'px-2 py-1 text-xs' : 'px-3 py-1.5 text-xs'}
            font-medium rounded-md transition-all
          `}
          style={{
            background: value === range.key ? colors.ui.accent : 'transparent',
            color: value === range.key ? colors.ui.text.primary : colors.ui.text.muted,
            boxShadow: value === range.key ? `0 0 12px ${colors.ui.accentGlow}` : 'none',
            transitionDuration: animations.duration.fast,
          }}
        >
          {range.label}
        </button>
      ))}
    </div>
  );
}
