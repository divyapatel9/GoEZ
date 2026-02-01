import { NavLink } from 'react-router-dom'
import { Home, BarChart3, Brain, History, Settings, Activity } from 'lucide-react'
import clsx from 'clsx'

const navItems = [
  { path: '/', icon: Home, label: 'Overview' },
  { path: '/visual-analytics', icon: BarChart3, label: 'Visual Analytics' },
  { path: '/deep-analysis', icon: Brain, label: 'Deep Analysis' },
  { path: '/sessions', icon: History, label: 'Sessions' },
  { path: '/settings', icon: Settings, label: 'Settings' },
]

export function Sidebar() {
  return (
    <aside 
      className="w-64 flex flex-col border-r"
      style={{ 
        background: 'var(--bg-secondary)',
        borderColor: 'var(--ui-border)',
      }}
    >
      <div className="p-6 border-b" style={{ borderColor: 'var(--ui-border)' }}>
        <div className="flex items-center gap-3">
          <div 
            className="w-10 h-10 rounded-xl flex items-center justify-center"
            style={{ background: 'linear-gradient(135deg, var(--accent-blue), var(--accent-purple))' }}
          >
            <Activity className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="font-bold" style={{ color: 'var(--ui-text-primary)' }}>
              Health Intelligence
            </h1>
            <p className="text-xs" style={{ color: 'var(--ui-text-muted)' }}>
              Your health, understood
            </p>
          </div>
        </div>
      </div>

      <nav className="flex-1 p-4 space-y-1">
        {navItems.map(({ path, icon: Icon, label }) => (
          <NavLink
            key={path}
            to={path}
            className={({ isActive }) => clsx(
              'flex items-center gap-3 px-4 py-3 rounded-lg transition-colors',
              isActive 
                ? 'bg-white/10' 
                : 'hover:bg-white/5'
            )}
            style={({ isActive }) => ({
              color: isActive ? 'var(--ui-text-primary)' : 'var(--ui-text-secondary)',
            })}
          >
            <Icon className="w-5 h-5" />
            <span className="font-medium">{label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="p-4 border-t" style={{ borderColor: 'var(--ui-border)' }}>
        <p className="text-xs text-center" style={{ color: 'var(--ui-text-muted)' }}>
          v1.0.0 • Unified App
        </p>
      </div>
    </aside>
  )
}
