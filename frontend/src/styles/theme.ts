/**
 * Premium Dark Theme Design System
 * WHOOP / Apple Fitness inspired visual language
 */

export const colors = {
  // Backgrounds
  bg: {
    primary: '#1a1a24',
    card: 'rgba(30, 30, 42, 0.9)',
    cardHover: 'rgba(40, 40, 55, 0.95)',
    glass: 'rgba(255, 255, 255, 0.05)',
    glassHover: 'rgba(255, 255, 255, 0.08)',
  },

  // Semantic Colors - Recovery States
  recovery: {
    ready: {
      primary: '#00ff94',
      glow: 'rgba(0, 255, 148, 0.4)',
      gradient: 'linear-gradient(135deg, #00ff94 0%, #00d4aa 100%)',
    },
    caution: {
      primary: '#ffb800',
      glow: 'rgba(255, 184, 0, 0.4)',
      gradient: 'linear-gradient(135deg, #ffb800 0%, #ff9500 100%)',
    },
    recover: {
      primary: '#ff4757',
      glow: 'rgba(255, 71, 87, 0.4)',
      gradient: 'linear-gradient(135deg, #ff4757 0%, #ff6b7a 100%)',
    },
  },

  // Metric Colors
  metrics: {
    hrv: '#00d4ff',
    rhr: '#ff00aa',
    strain: '#a855f7',
    steps: '#3b82f6',
    energy: '#f59e0b',
    exercise: '#10b981',
    flights: '#8b5cf6',
    baseline: 'rgba(100, 100, 255, 0.3)',
  },

  // UI Colors
  ui: {
    text: {
      primary: '#ffffff',
      secondary: 'rgba(255, 255, 255, 0.7)',
      muted: 'rgba(255, 255, 255, 0.4)',
      disabled: 'rgba(255, 255, 255, 0.2)',
    },
    border: 'rgba(255, 255, 255, 0.08)',
    borderHover: 'rgba(255, 255, 255, 0.15)',
    accent: '#6366f1',
    accentGlow: 'rgba(99, 102, 241, 0.4)',
  },

  // State Colors
  state: {
    good: '#00ff94',
    warning: '#ffb800',
    danger: '#ff4757',
    neutral: '#6b7280',
    missing: 'rgba(255, 255, 255, 0.1)',
  },
};

export const shadows = {
  glow: {
    green: '0 0 20px rgba(0, 255, 148, 0.3), 0 0 40px rgba(0, 255, 148, 0.1)',
    yellow: '0 0 20px rgba(255, 184, 0, 0.3), 0 0 40px rgba(255, 184, 0, 0.1)',
    red: '0 0 20px rgba(255, 71, 87, 0.3), 0 0 40px rgba(255, 71, 87, 0.1)',
    blue: '0 0 20px rgba(0, 212, 255, 0.3), 0 0 40px rgba(0, 212, 255, 0.1)',
    purple: '0 0 20px rgba(168, 85, 247, 0.3), 0 0 40px rgba(168, 85, 247, 0.1)',
  },
  card: '0 4px 24px rgba(0, 0, 0, 0.4), 0 0 1px rgba(255, 255, 255, 0.1)',
  cardHover: '0 8px 32px rgba(0, 0, 0, 0.5), 0 0 1px rgba(255, 255, 255, 0.15)',
};

export const gradients = {
  arcGreen: 'conic-gradient(from 180deg, #00ff94 0deg, #00d4aa 120deg)',
  arcYellow: 'conic-gradient(from 180deg, #ffb800 0deg, #ff9500 120deg)',
  arcRed: 'conic-gradient(from 180deg, #ff4757 0deg, #ff6b7a 120deg)',
  recoveryArc: 'conic-gradient(from 180deg, #ff4757 0deg, #ffb800 120deg, #00ff94 180deg)',
  glassCard: 'linear-gradient(135deg, rgba(255,255,255,0.05) 0%, rgba(255,255,255,0.02) 100%)',
  heroGlow: 'radial-gradient(circle at 50% 50%, rgba(99, 102, 241, 0.15) 0%, transparent 70%)',
};

export const animations = {
  duration: {
    fast: '150ms',
    normal: '250ms',
    slow: '400ms',
  },
  easing: {
    smooth: 'cubic-bezier(0.4, 0, 0.2, 1)',
    bounce: 'cubic-bezier(0.34, 1.56, 0.64, 1)',
    spring: 'cubic-bezier(0.175, 0.885, 0.32, 1.275)',
  },
};

export const typography = {
  score: {
    fontSize: '4rem',
    fontWeight: '700',
    letterSpacing: '-0.02em',
  },
  heading: {
    fontSize: '1.25rem',
    fontWeight: '600',
    letterSpacing: '-0.01em',
  },
  label: {
    fontSize: '0.875rem',
    fontWeight: '500',
  },
  caption: {
    fontSize: '0.75rem',
    fontWeight: '400',
  },
};

export function getRecoveryColor(score: number | null): keyof typeof colors.recovery {
  if (score === null) return 'recover';
  if (score >= 67) return 'ready';
  if (score >= 34) return 'caution';
  return 'recover';
}

export function getRecoveryStyles(score: number | null) {
  const state = getRecoveryColor(score);
  return {
    color: colors.recovery[state].primary,
    glow: colors.recovery[state].glow,
    gradient: colors.recovery[state].gradient,
    shadow: shadows.glow[state === 'ready' ? 'green' : state === 'caution' ? 'yellow' : 'red'],
  };
}
