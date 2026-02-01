import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { TrendingUp, TrendingDown, Minus, AlertTriangle, Brain, BarChart3 } from 'lucide-react'
import { analyticsApi } from '@/services'
import { useContextStore } from '@/store/contextStore'
import type { OverviewTile } from '@/services/analytics_api'

export function Overview() {
  const [tiles, setTiles] = useState<OverviewTile[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()
  const setContext = useContextStore((s) => s.setContext)

  useEffect(() => {
    async function fetchOverview() {
      try {
        const data = await analyticsApi.getOverview()
        setTiles(data.tiles)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load overview')
      } finally {
        setLoading(false)
      }
    }
    fetchOverview()
  }, [])

  const handleViewInVisualAnalytics = (tile: OverviewTile) => {
    setContext({
      source: 'overview',
      metrics: [tile.metric_key],
      dateRange: { start: '', end: '' },
    })
    navigate('/visual-analytics')
  }

  const handleRunDeepAnalysis = (tile: OverviewTile) => {
    setContext({
      source: 'overview',
      metrics: [tile.metric_key],
      dateRange: { start: '', end: '' },
      observation: `Analyze my ${tile.display_name} trends and provide insights.`,
    })
    navigate('/deep-analysis')
  }

  const getTrendIcon = (trend: 'up' | 'down' | 'flat') => {
    switch (trend) {
      case 'up': return <TrendingUp className="w-4 h-4 text-green-400" />
      case 'down': return <TrendingDown className="w-4 h-4 text-red-400" />
      default: return <Minus className="w-4 h-4 text-gray-400" />
    }
  }

  const getAnomalyBadge = (level: 'none' | 'mild' | 'strong') => {
    if (level === 'none') return null
    return (
      <span className={`px-2 py-0.5 rounded text-xs font-medium ${
        level === 'strong' ? 'bg-red-500/20 text-red-400' : 'bg-yellow-500/20 text-yellow-400'
      }`}>
        <AlertTriangle className="w-3 h-3 inline mr-1" />
        {level === 'strong' ? 'Alert' : 'Notice'}
      </span>
    )
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-pulse" style={{ color: 'var(--ui-text-muted)' }}>
          Loading health overview...
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <p style={{ color: 'var(--accent-red)' }}>{error}</p>
          <p className="text-sm mt-2" style={{ color: 'var(--ui-text-muted)' }}>
            Make sure the backend server is running.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="p-6">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8">
          <h2 className="text-2xl font-bold" style={{ color: 'var(--ui-text-primary)' }}>
            Health Overview
          </h2>
          <p style={{ color: 'var(--ui-text-muted)' }}>
            Your key health metrics at a glance
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {tiles.map((tile) => (
            <div
              key={tile.metric_key}
              className="rounded-xl p-5 transition-all hover:scale-[1.02]"
              style={{ 
                background: 'var(--bg-card)', 
                border: '1px solid var(--ui-border)' 
              }}
            >
              <div className="flex items-start justify-between mb-3">
                <div>
                  <h3 className="font-medium" style={{ color: 'var(--ui-text-primary)' }}>
                    {tile.display_name}
                  </h3>
                  <p className="text-xs" style={{ color: 'var(--ui-text-muted)' }}>
                    {tile.latest_date}
                  </p>
                </div>
                {getAnomalyBadge(tile.anomaly_level)}
              </div>

              <div className="flex items-baseline gap-2 mb-3">
                <span className="text-3xl font-bold" style={{ color: 'var(--ui-text-primary)' }}>
                  {tile.latest_value.toLocaleString(undefined, { maximumFractionDigits: 1 })}
                </span>
                <span className="text-sm" style={{ color: 'var(--ui-text-muted)' }}>
                  {tile.unit}
                </span>
              </div>

              <div className="flex items-center gap-3 mb-4">
                <div className="flex items-center gap-1">
                  {getTrendIcon(tile.trend_7d)}
                  <span className="text-xs" style={{ color: 'var(--ui-text-secondary)' }}>
                    7d trend
                  </span>
                </div>
                {tile.delta_percent !== null && tile.delta_percent !== undefined && (
                  <span className={`text-xs ${
                    tile.delta_percent > 0 ? 'text-green-400' : 
                    tile.delta_percent < 0 ? 'text-red-400' : ''
                  }`} style={{ color: tile.delta_percent === 0 ? 'var(--ui-text-muted)' : undefined }}>
                    {tile.delta_percent > 0 ? '+' : ''}{tile.delta_percent.toFixed(1)}% vs baseline
                  </span>
                )}
              </div>

              <div className="flex gap-2">
                <button
                  onClick={() => handleViewInVisualAnalytics(tile)}
                  className="flex-1 px-3 py-2 rounded-lg text-xs font-medium transition-colors hover:bg-white/10 flex items-center justify-center gap-1"
                  style={{ 
                    border: '1px solid var(--ui-border)',
                    color: 'var(--ui-text-secondary)'
                  }}
                >
                  <BarChart3 className="w-3 h-3" />
                  View Charts
                </button>
                <button
                  onClick={() => handleRunDeepAnalysis(tile)}
                  className="flex-1 px-3 py-2 rounded-lg text-xs font-medium transition-colors flex items-center justify-center gap-1"
                  style={{ 
                    background: 'linear-gradient(135deg, var(--accent-blue), var(--accent-purple))',
                    color: 'white'
                  }}
                >
                  <Brain className="w-3 h-3" />
                  Deep Analysis
                </button>
              </div>
            </div>
          ))}
        </div>

        {tiles.length === 0 && (
          <div className="text-center py-12">
            <p style={{ color: 'var(--ui-text-muted)' }}>
              No health data available. Make sure your data is loaded.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
