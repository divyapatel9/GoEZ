import { useState } from 'react'
import { Sparkles, X } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useContextStore } from '@/store/contextStore'

export function FloatingAIButton() {
  const [isOpen, setIsOpen] = useState(false)
  const navigate = useNavigate()
  const setContext = useContextStore((s) => s.setContext)

  const handleDeepAnalysis = () => {
    setContext({
      source: 'overview',
      metrics: [],
      dateRange: { start: '', end: '' },
    })
    navigate('/deep-analysis')
    setIsOpen(false)
  }

  return (
    <>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="fixed bottom-6 right-6 w-14 h-14 rounded-full shadow-lg flex items-center justify-center z-50 transition-transform hover:scale-110"
        style={{
          background: 'linear-gradient(135deg, var(--accent-blue), var(--accent-purple))',
        }}
      >
        {isOpen ? (
          <X className="w-6 h-6 text-white" />
        ) : (
          <Sparkles className="w-6 h-6 text-white" />
        )}
      </button>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.95 }}
            className="fixed bottom-24 right-6 w-80 rounded-xl shadow-2xl z-50 overflow-hidden"
            style={{ background: 'var(--bg-card)', border: '1px solid var(--ui-border)' }}
          >
            <div className="p-4 border-b" style={{ borderColor: 'var(--ui-border)' }}>
              <h3 className="font-semibold" style={{ color: 'var(--ui-text-primary)' }}>
                AI Assistant
              </h3>
              <p className="text-sm mt-1" style={{ color: 'var(--ui-text-muted)' }}>
                How can I help you today?
              </p>
            </div>
            <div className="p-4 space-y-3">
              <button
                onClick={handleDeepAnalysis}
                className="w-full p-3 rounded-lg text-left transition-colors hover:bg-white/5"
                style={{ color: 'var(--ui-text-primary)' }}
              >
                <div className="font-medium">Deep Analysis</div>
                <div className="text-sm" style={{ color: 'var(--ui-text-muted)' }}>
                  Get comprehensive AI-powered insights
                </div>
              </button>
              <button
                onClick={() => {
                  navigate('/visual-analytics')
                  setIsOpen(false)
                }}
                className="w-full p-3 rounded-lg text-left transition-colors hover:bg-white/5"
                style={{ color: 'var(--ui-text-primary)' }}
              >
                <div className="font-medium">Visual Analytics</div>
                <div className="text-sm" style={{ color: 'var(--ui-text-muted)' }}>
                  Explore charts and trends
                </div>
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
