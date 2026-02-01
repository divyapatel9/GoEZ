import { useNavigate } from 'react-router-dom'
import { Clock, Brain, BarChart3, Home, Trash2 } from 'lucide-react'
import { useSessionStore, SessionRecord } from '@/store/sessionStore'

export function Sessions() {
  const { sessions, removeSession, clearSessions } = useSessionStore()
  const navigate = useNavigate()

  const getSourceIcon = (source: SessionRecord['source']) => {
    switch (source) {
      case 'overview': return <Home className="w-4 h-4" />
      case 'visual_analytics': return <BarChart3 className="w-4 h-4" />
      case 'deep_analysis': return <Brain className="w-4 h-4" />
    }
  }

  const getSourceLabel = (source: SessionRecord['source']) => {
    switch (source) {
      case 'overview': return 'Overview'
      case 'visual_analytics': return 'Visual Analytics'
      case 'deep_analysis': return 'Deep Analysis'
    }
  }

  const formatDate = (timestamp: string) => {
    const date = new Date(timestamp)
    return date.toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  const handleOpenSession = (session: SessionRecord) => {
    if (session.source === 'deep_analysis') {
      navigate('/deep-analysis')
    } else if (session.source === 'visual_analytics') {
      navigate('/visual-analytics')
    } else {
      navigate('/')
    }
  }

  return (
    <div className="p-6">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h2 className="text-2xl font-bold" style={{ color: 'var(--ui-text-primary)' }}>
              Session History
            </h2>
            <p style={{ color: 'var(--ui-text-muted)' }}>
              Your recent analysis sessions
            </p>
          </div>
          {sessions.length > 0 && (
            <button
              onClick={() => {
                if (confirm('Clear all session history?')) {
                  clearSessions()
                }
              }}
              className="px-4 py-2 rounded-lg text-sm transition-colors hover:bg-white/10"
              style={{ 
                border: '1px solid var(--ui-border)',
                color: 'var(--ui-text-secondary)'
              }}
            >
              Clear All
            </button>
          )}
        </div>

        {sessions.length === 0 ? (
          <div 
            className="text-center py-16 rounded-xl"
            style={{ 
              background: 'var(--bg-card)', 
              border: '1px solid var(--ui-border)' 
            }}
          >
            <Clock className="w-12 h-12 mx-auto mb-4" style={{ color: 'var(--ui-text-muted)' }} />
            <h3 className="text-lg font-medium mb-2" style={{ color: 'var(--ui-text-primary)' }}>
              No sessions yet
            </h3>
            <p style={{ color: 'var(--ui-text-muted)' }}>
              Your analysis history will appear here as you use the app.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {sessions.map((session) => (
              <div
                key={session.id}
                className="rounded-xl p-4 transition-all hover:bg-white/5 cursor-pointer group"
                style={{ 
                  background: 'var(--bg-card)', 
                  border: '1px solid var(--ui-border)' 
                }}
                onClick={() => handleOpenSession(session)}
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-3">
                    <div 
                      className="w-10 h-10 rounded-lg flex items-center justify-center"
                      style={{ background: 'var(--ui-border)' }}
                    >
                      {getSourceIcon(session.source)}
                    </div>
                    <div>
                      <h4 className="font-medium" style={{ color: 'var(--ui-text-primary)' }}>
                        {session.label}
                      </h4>
                      <div className="flex items-center gap-2 mt-1">
                        <span 
                          className="text-xs px-2 py-0.5 rounded"
                          style={{ background: 'var(--ui-border)', color: 'var(--ui-text-secondary)' }}
                        >
                          {getSourceLabel(session.source)}
                        </span>
                        <span className="text-xs" style={{ color: 'var(--ui-text-muted)' }}>
                          {formatDate(session.timestamp)}
                        </span>
                      </div>
                      {session.preview && (
                        <p 
                          className="text-sm mt-2 line-clamp-2"
                          style={{ color: 'var(--ui-text-secondary)' }}
                        >
                          {session.preview}
                        </p>
                      )}
                    </div>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      removeSession(session.id)
                    }}
                    className="p-2 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity hover:bg-white/10"
                    style={{ color: 'var(--ui-text-muted)' }}
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
