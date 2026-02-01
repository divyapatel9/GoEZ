import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { Header } from './Header'
import { AIDock, SparkleButton } from '@/shared/ui'

export function AppLayout() {
  const [aiDockOpen, setAiDockOpen] = useState(false)

  return (
    <div className="flex h-screen" style={{ background: 'var(--bg-primary)' }}>
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-auto">
          <Outlet />
        </main>
      </div>
      <SparkleButton onClick={() => setAiDockOpen(true)} isOpen={aiDockOpen} />
      <AIDock isOpen={aiDockOpen} onClose={() => setAiDockOpen(false)} />
    </div>
  )
}
