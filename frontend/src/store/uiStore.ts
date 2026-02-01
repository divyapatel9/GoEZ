import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface UIState {
  sidebarCollapsed: boolean
  theme: 'dark' | 'light'
  defaultDateRange: '7d' | '30d' | '90d'
  aiVerbosity: 'concise' | 'detailed'
  toggleSidebar: () => void
  setTheme: (theme: 'dark' | 'light') => void
  setDefaultDateRange: (range: '7d' | '30d' | '90d') => void
  setAiVerbosity: (verbosity: 'concise' | 'detailed') => void
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      sidebarCollapsed: false,
      theme: 'dark',
      defaultDateRange: '30d',
      aiVerbosity: 'detailed',
      toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
      setTheme: (theme) => set({ theme }),
      setDefaultDateRange: (defaultDateRange) => set({ defaultDateRange }),
      setAiVerbosity: (aiVerbosity) => set({ aiVerbosity }),
    }),
    { name: 'health-ui-store' }
  )
)
