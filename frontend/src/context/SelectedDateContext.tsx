/**
 * Shared context for cross-chart date selection.
 * When a user clicks a day in any insight card, this context propagates
 * that selection to other charts (especially Raw Metrics Explorer).
 */

import { createContext, useContext, useState, useCallback, type ReactNode } from 'react';

interface SelectedDateState {
  date: string | null;
  source: string | null; // Which card triggered the selection
}

interface SelectedDateContextValue {
  selectedDate: SelectedDateState;
  setSelectedDate: (date: string | null, source?: string) => void;
  clearSelectedDate: () => void;
}

const SelectedDateContext = createContext<SelectedDateContextValue | null>(null);

export function SelectedDateProvider({ children }: { children: ReactNode }) {
  const [selectedDate, setSelectedDateState] = useState<SelectedDateState>({
    date: null,
    source: null,
  });

  const setSelectedDate = useCallback((date: string | null, source?: string) => {
    setSelectedDateState({ date, source: source ?? null });
  }, []);

  const clearSelectedDate = useCallback(() => {
    setSelectedDateState({ date: null, source: null });
  }, []);

  return (
    <SelectedDateContext.Provider value={{ selectedDate, setSelectedDate, clearSelectedDate }}>
      {children}
    </SelectedDateContext.Provider>
  );
}

export function useSelectedDate() {
  const context = useContext(SelectedDateContext);
  if (!context) {
    throw new Error('useSelectedDate must be used within a SelectedDateProvider');
  }
  return context;
}
