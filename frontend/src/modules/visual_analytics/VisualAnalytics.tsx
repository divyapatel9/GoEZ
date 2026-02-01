/**
 * Visual Analytics Module
 * 
 * Premium Health Dashboard with WHOOP-style charts
 * This module displays charts and analytics from the /analytics/* endpoints
 */

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Brain } from 'lucide-react'
import { useContextStore } from '@/store/contextStore'
import { colors } from '@/styles/theme'
import { AIDock, SparkleButton } from '@/shared/ui'
import { 
  RecoveryGauge, 
  RecoveryStrainQuadrant,
  HrvRhrTrend,
  EffortComposition,
  ReadinessTimeline,
  MovementEfficiency,
  LifestyleVsExercise,
  RawMetricsExplorer,
} from './components'

export function VisualAnalytics() {
  const [aiDockOpen, setAiDockOpen] = useState(false)
  const navigate = useNavigate()
  const setContext = useContextStore((s) => s.setContext)

  const handleRunDeepAnalysis = () => {
    setContext({
      source: 'visual_analytics',
      metrics: [],
      dateRange: { start: '', end: '' },
      observation: 'Analyze my overall health trends based on what I see in the dashboard.',
    })
    navigate('/deep-analysis')
  }

  return (
    <div 
      className="min-h-full p-6"
      style={{ background: colors.bg.primary }}
    >
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <header className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold" style={{ color: colors.ui.text.primary }}>
              Visual Analytics
            </h1>
            <p style={{ color: colors.ui.text.muted }}>
              Explore your health trends with interactive charts
            </p>
          </div>
          <button
            onClick={handleRunDeepAnalysis}
            className="px-4 py-2 rounded-lg font-medium flex items-center gap-2 transition-transform hover:scale-105"
            style={{ 
              background: `linear-gradient(135deg, ${colors.ui.accent}, ${colors.metrics.strain})`,
              color: 'white'
            }}
          >
            <Brain className="w-4 h-4" />
            Run Deep Analysis
          </button>
        </header>

        {/* Premium Charts Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          <RecoveryGauge initialRange="7d" />
          <RecoveryStrainQuadrant initialRange="30d" />
        </div>

        <div className="mb-6">
          <HrvRhrTrend initialRange="30d" />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          <EffortComposition initialRange="30d" />
          <ReadinessTimeline initialRange="30d" />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <MovementEfficiency initialRange="30d" />
          <LifestyleVsExercise initialRange="30d" />
        </div>

        {/* Raw Metrics Explorer */}
        <div className="mt-8">
          <RawMetricsExplorer />
        </div>

        {/* Footer */}
        <footer 
          className="mt-10 pt-6 text-center text-xs"
          style={{ 
            borderTop: `1px solid ${colors.ui.border}`,
            color: colors.ui.text.muted 
          }}
        >
          <p>
            These insights are relative to your personal baseline and do not constitute medical advice.
          </p>
          <p className="mt-2" style={{ color: colors.ui.text.disabled }}>
            Each card has its own time selector — adjust ranges independently to explore your data.
          </p>
        </footer>
      </div>

      {/* AI Coach */}
      <SparkleButton onClick={() => setAiDockOpen(true)} isOpen={aiDockOpen} />
      <AIDock isOpen={aiDockOpen} onClose={() => setAiDockOpen(false)} />
    </div>
  )
}

