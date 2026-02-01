import { create } from 'zustand'

export interface AnalysisContext {
  source: 'overview' | 'visual_analytics'
  metrics: string[]
  dateRange: { start: string; end: string }
  observation?: string
}

interface ContextState {
  context: AnalysisContext | null
  setContext: (context: AnalysisContext) => void
  clearContext: () => void
}

export const useContextStore = create<ContextState>((set) => ({
  context: null,
  setContext: (context) => set({ context }),
  clearContext: () => set({ context: null }),
}))
