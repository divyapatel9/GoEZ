import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export interface SessionRecord {
  id: string
  source: 'overview' | 'visual_analytics' | 'deep_analysis'
  label: string
  timestamp: string
  backendSessionId?: string
  metrics?: string[]
  preview?: string
}

interface SessionState {
  sessions: SessionRecord[]
  addSession: (session: Omit<SessionRecord, 'id' | 'timestamp'>) => string
  updateSession: (id: string, updates: Partial<SessionRecord>) => void
  removeSession: (id: string) => void
  clearSessions: () => void
}

export const useSessionStore = create<SessionState>()(
  persist(
    (set, get) => ({
      sessions: [],
      addSession: (session) => {
        const id = crypto.randomUUID()
        const newSession: SessionRecord = {
          ...session,
          id,
          timestamp: new Date().toISOString(),
        }
        set((s) => ({ sessions: [newSession, ...s.sessions].slice(0, 100) }))
        return id
      },
      updateSession: (id, updates) => {
        set((s) => ({
          sessions: s.sessions.map((sess) =>
            sess.id === id ? { ...sess, ...updates } : sess
          ),
        }))
      },
      removeSession: (id) => {
        set((s) => ({ sessions: s.sessions.filter((sess) => sess.id !== id) }))
      },
      clearSessions: () => set({ sessions: [] }),
    }),
    { name: 'health-sessions' }
  )
)
