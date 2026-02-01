/**
 * Glassmorphism Card Wrapper
 * Premium dark theme card with subtle glow and glass effect
 */

import type { ReactNode } from 'react';
import { colors, shadows, gradients, animations } from '../../styles/theme';

interface GlassCardProps {
  children: ReactNode;
  className?: string;
  glow?: 'green' | 'yellow' | 'red' | 'blue' | 'purple' | 'none';
  padding?: 'sm' | 'md' | 'lg';
}

export function GlassCard({ 
  children, 
  className = '', 
  glow = 'none',
  padding = 'md' 
}: GlassCardProps) {
  const paddingStyles = {
    sm: 'p-4',
    md: 'p-6',
    lg: 'p-8',
  };

  const glowStyle = glow !== 'none' ? shadows.glow[glow] : 'none';

  return (
    <div
      className={`relative rounded-2xl overflow-hidden ${paddingStyles[padding]} ${className}`}
      style={{
        background: gradients.glassCard,
        backgroundColor: colors.bg.card,
        border: `1px solid ${colors.ui.border}`,
        boxShadow: `${shadows.card}${glow !== 'none' ? `, ${glowStyle}` : ''}`,
        backdropFilter: 'blur(20px)',
        transition: `all ${animations.duration.normal} ${animations.easing.smooth}`,
      }}
    >
      {children}
    </div>
  );
}

interface CardHeaderProps {
  title: string;
  subtitle?: string;
  rightContent?: ReactNode;
}

export function CardHeader({ title, subtitle, rightContent }: CardHeaderProps) {
  return (
    <div className="flex items-start justify-between mb-4">
      <div>
        <h2 
          className="text-lg font-semibold"
          style={{ color: colors.ui.text.primary }}
        >
          {title}
        </h2>
        {subtitle && (
          <p 
            className="text-sm mt-0.5"
            style={{ color: colors.ui.text.muted }}
          >
            {subtitle}
          </p>
        )}
      </div>
      {rightContent && (
        <div className="flex-shrink-0">
          {rightContent}
        </div>
      )}
    </div>
  );
}

interface TeachingLineProps {
  text: string;
  direction?: 'higher' | 'lower' | 'balanced' | 'baseline';
}

export function TeachingLine({ text, direction }: TeachingLineProps) {
  const directionLabels = {
    higher: '↑ Higher is better',
    lower: '↓ Lower is better',
    balanced: '⚖ Balanced is better',
    baseline: '◎ Closer to baseline is better',
  };

  return (
    <div 
      className="mt-4 pt-4 text-center"
      style={{ borderTop: `1px solid ${colors.ui.border}` }}
    >
      <p 
        className="text-xs"
        style={{ color: colors.ui.text.muted }}
      >
        {text}
      </p>
      {direction && (
        <span 
          className="inline-block mt-1.5 px-2 py-0.5 rounded-full text-xs font-medium"
          style={{ 
            background: colors.bg.glass,
            color: colors.ui.text.secondary,
          }}
        >
          {directionLabels[direction]}
        </span>
      )}
    </div>
  );
}

interface InsightBadgeProps {
  text: string;
  variant?: 'good' | 'warning' | 'danger' | 'neutral';
}

export function InsightBadge({ text, variant = 'neutral' }: InsightBadgeProps) {
  const variantColors = {
    good: { bg: 'rgba(0, 255, 148, 0.15)', text: colors.state.good },
    warning: { bg: 'rgba(255, 184, 0, 0.15)', text: colors.state.warning },
    danger: { bg: 'rgba(255, 71, 87, 0.15)', text: colors.state.danger },
    neutral: { bg: colors.bg.glass, text: colors.ui.text.secondary },
  };

  return (
    <span
      className="inline-flex items-center px-3 py-1.5 rounded-lg text-xs font-medium"
      style={{
        background: variantColors[variant].bg,
        color: variantColors[variant].text,
      }}
    >
      {text}
    </span>
  );
}
