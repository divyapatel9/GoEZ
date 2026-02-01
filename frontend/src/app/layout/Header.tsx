import { useLocation } from 'react-router-dom'
import { Bell, User } from 'lucide-react'

const pageTitles: Record<string, { title: string; description: string }> = {
  '/': { title: 'Overview', description: 'Your health at a glance' },
  '/visual-analytics': { title: 'Visual Analytics', description: 'Explore your health trends' },
  '/deep-analysis': { title: 'Deep Analysis', description: 'AI-powered health insights' },
  '/sessions': { title: 'Sessions', description: 'Your analysis history' },
  '/settings': { title: 'Settings', description: 'Customize your experience' },
}

export function Header() {
  const location = useLocation()
  const { title, description } = pageTitles[location.pathname] || { 
    title: 'Health Intelligence', 
    description: '' 
  }

  return (
    <header 
      className="h-16 flex items-center justify-between px-6 border-b"
      style={{ 
        background: 'var(--bg-secondary)',
        borderColor: 'var(--ui-border)',
      }}
    >
      <div>
        <h2 className="text-lg font-semibold" style={{ color: 'var(--ui-text-primary)' }}>
          {title}
        </h2>
        {description && (
          <p className="text-sm" style={{ color: 'var(--ui-text-muted)' }}>
            {description}
          </p>
        )}
      </div>

      <div className="flex items-center gap-4">
        <button 
          className="p-2 rounded-lg hover:bg-white/5 transition-colors"
          style={{ color: 'var(--ui-text-secondary)' }}
        >
          <Bell className="w-5 h-5" />
        </button>
        <button 
          className="w-9 h-9 rounded-full flex items-center justify-center"
          style={{ background: 'var(--ui-border)', color: 'var(--ui-text-secondary)' }}
        >
          <User className="w-5 h-5" />
        </button>
      </div>
    </header>
  )
}
