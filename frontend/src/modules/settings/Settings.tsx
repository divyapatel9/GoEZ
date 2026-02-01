import { useState, useEffect } from 'react'
import { Check, AlertCircle, RefreshCw } from 'lucide-react'
import { useUIStore } from '@/store/uiStore'
import { agentApi, analyticsApi, aiApi } from '@/services'

interface HealthStatus {
  agent: { status: 'checking' | 'healthy' | 'error'; message?: string }
  analytics: { status: 'checking' | 'healthy' | 'error'; message?: string }
  ai: { status: 'checking' | 'healthy' | 'error'; message?: string }
}

export function Settings() {
  const { 
    defaultDateRange, 
    aiVerbosity, 
    setDefaultDateRange, 
    setAiVerbosity 
  } = useUIStore()

  const [health, setHealth] = useState<HealthStatus>({
    agent: { status: 'checking' },
    analytics: { status: 'checking' },
    ai: { status: 'checking' },
  })

  const checkHealth = async () => {
    setHealth({
      agent: { status: 'checking' },
      analytics: { status: 'checking' },
      ai: { status: 'checking' },
    })

    // Check agent health
    try {
      await agentApi.checkHealth()
      setHealth((h) => ({ ...h, agent: { status: 'healthy' } }))
    } catch (err) {
      setHealth((h) => ({ 
        ...h, 
        agent: { status: 'error', message: err instanceof Error ? err.message : 'Failed' } 
      }))
    }

    // Check analytics health
    try {
      await analyticsApi.checkHealth()
      setHealth((h) => ({ ...h, analytics: { status: 'healthy' } }))
    } catch (err) {
      setHealth((h) => ({ 
        ...h, 
        analytics: { status: 'error', message: err instanceof Error ? err.message : 'Failed' } 
      }))
    }

    // Check AI health
    try {
      const result = await aiApi.checkAIHealth()
      setHealth((h) => ({ 
        ...h, 
        ai: { 
          status: result.api_key_configured ? 'healthy' : 'error',
          message: result.api_key_configured ? undefined : 'API key not configured'
        } 
      }))
    } catch (err) {
      setHealth((h) => ({ 
        ...h, 
        ai: { status: 'error', message: err instanceof Error ? err.message : 'Failed' } 
      }))
    }
  }

  useEffect(() => {
    checkHealth()
  }, [])

  const getStatusIcon = (status: 'checking' | 'healthy' | 'error') => {
    switch (status) {
      case 'checking':
        return <RefreshCw className="w-4 h-4 animate-spin" style={{ color: 'var(--ui-text-muted)' }} />
      case 'healthy':
        return <Check className="w-4 h-4 text-green-400" />
      case 'error':
        return <AlertCircle className="w-4 h-4 text-red-400" />
    }
  }

  return (
    <div className="p-6">
      <div className="max-w-2xl mx-auto space-y-8">
        <div>
          <h2 className="text-2xl font-bold" style={{ color: 'var(--ui-text-primary)' }}>
            Settings
          </h2>
          <p style={{ color: 'var(--ui-text-muted)' }}>
            Customize your experience
          </p>
        </div>

        {/* Backend Health */}
        <section 
          className="rounded-xl p-6"
          style={{ background: 'var(--bg-card)', border: '1px solid var(--ui-border)' }}
        >
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold" style={{ color: 'var(--ui-text-primary)' }}>
              Backend Status
            </h3>
            <button
              onClick={checkHealth}
              className="px-3 py-1.5 rounded-lg text-sm transition-colors hover:bg-white/10 flex items-center gap-2"
              style={{ border: '1px solid var(--ui-border)', color: 'var(--ui-text-secondary)' }}
            >
              <RefreshCw className="w-3 h-3" />
              Refresh
            </button>
          </div>
          <div className="space-y-3">
            {[
              { key: 'agent', label: 'Deep Analysis (Agent)', ...health.agent },
              { key: 'analytics', label: 'Visual Analytics', ...health.analytics },
              { key: 'ai', label: 'AI Service', ...health.ai },
            ].map((service) => (
              <div 
                key={service.key}
                className="flex items-center justify-between py-2"
              >
                <div>
                  <span style={{ color: 'var(--ui-text-primary)' }}>{service.label}</span>
                  {service.message && (
                    <p className="text-xs mt-0.5" style={{ color: 'var(--ui-text-muted)' }}>
                      {service.message}
                    </p>
                  )}
                </div>
                {getStatusIcon(service.status)}
              </div>
            ))}
          </div>
        </section>

        {/* Preferences */}
        <section 
          className="rounded-xl p-6"
          style={{ background: 'var(--bg-card)', border: '1px solid var(--ui-border)' }}
        >
          <h3 className="font-semibold mb-4" style={{ color: 'var(--ui-text-primary)' }}>
            Preferences
          </h3>
          <div className="space-y-4">
            <div>
              <label className="block text-sm mb-2" style={{ color: 'var(--ui-text-secondary)' }}>
                Default Date Range
              </label>
              <div className="flex gap-2">
                {(['7d', '30d', '90d'] as const).map((range) => (
                  <button
                    key={range}
                    onClick={() => setDefaultDateRange(range)}
                    className={`px-4 py-2 rounded-lg text-sm transition-colors ${
                      defaultDateRange === range ? 'bg-white/10' : 'hover:bg-white/5'
                    }`}
                    style={{ 
                      border: '1px solid var(--ui-border)',
                      color: defaultDateRange === range ? 'var(--ui-text-primary)' : 'var(--ui-text-secondary)'
                    }}
                  >
                    {range === '7d' ? '7 Days' : range === '30d' ? '30 Days' : '90 Days'}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm mb-2" style={{ color: 'var(--ui-text-secondary)' }}>
                AI Response Style
              </label>
              <div className="flex gap-2">
                {(['concise', 'detailed'] as const).map((style) => (
                  <button
                    key={style}
                    onClick={() => setAiVerbosity(style)}
                    className={`px-4 py-2 rounded-lg text-sm transition-colors ${
                      aiVerbosity === style ? 'bg-white/10' : 'hover:bg-white/5'
                    }`}
                    style={{ 
                      border: '1px solid var(--ui-border)',
                      color: aiVerbosity === style ? 'var(--ui-text-primary)' : 'var(--ui-text-secondary)'
                    }}
                  >
                    {style === 'concise' ? 'Concise' : 'Detailed'}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* About */}
        <section 
          className="rounded-xl p-6"
          style={{ background: 'var(--bg-card)', border: '1px solid var(--ui-border)' }}
        >
          <h3 className="font-semibold mb-2" style={{ color: 'var(--ui-text-primary)' }}>
            About
          </h3>
          <p className="text-sm" style={{ color: 'var(--ui-text-muted)' }}>
            Health Intelligence App v1.0.0
          </p>
          <p className="text-sm mt-1" style={{ color: 'var(--ui-text-muted)' }}>
            A unified platform for visual health analytics and AI-powered deep analysis.
          </p>
        </section>
      </div>
    </div>
  )
}
