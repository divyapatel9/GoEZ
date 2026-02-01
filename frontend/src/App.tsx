import { Routes, Route } from 'react-router-dom'
import { AppLayout } from './app/layout/AppLayout'
import { Overview } from './modules/overview/Overview'
import { VisualAnalytics } from './modules/visual_analytics/VisualAnalytics'
import { DeepAnalysis } from './modules/deep_analysis/DeepAnalysis'
import { Sessions } from './modules/sessions/Sessions'
import { Settings } from './modules/settings/Settings'

function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<Overview />} />
        <Route path="/visual-analytics" element={<VisualAnalytics />} />
        <Route path="/deep-analysis" element={<DeepAnalysis />} />
        <Route path="/sessions" element={<Sessions />} />
        <Route path="/settings" element={<Settings />} />
      </Route>
    </Routes>
  )
}

export default App
