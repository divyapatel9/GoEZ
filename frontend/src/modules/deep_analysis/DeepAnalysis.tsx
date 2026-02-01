/**
 * Deep Analysis Module
 * 
 * Migrated from health-hackathon-PANW/frontend - Agent Chat Interface
 * This module provides AI-powered deep health analysis via /agent/* endpoints
 */

import { useState, useEffect, useRef, useCallback } from 'react'
import { Send, Loader2, MessageSquare, ChevronLeft } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { agentApi } from '@/services'
import { useContextStore } from '@/store/contextStore'
import { useSessionStore } from '@/store/sessionStore'
import type { StreamEvent } from '@/services/agent_api'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  phase?: string
}

type Phase = 'idle' | 'clarify' | 'planning' | 'analyzing' | 'writing' | 'complete'

const phaseDescriptions: Record<Phase, string> = {
  idle: '',
  clarify: 'Understanding your question...',
  planning: 'Planning analysis approach...',
  analyzing: 'Analyzing health data...',
  writing: 'Generating insights...',
  complete: 'Analysis complete',
}

export function DeepAnalysis() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [phase, setPhase] = useState<Phase>('idle')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [currentContent, setCurrentContent] = useState('')
  
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const abortControllerRef = useRef<AbortController | null>(null)
  const contentRef = useRef<string>('')
  
  const navigate = useNavigate()
  const { context, clearContext } = useContextStore()
  const addSession = useSessionStore((s) => s.addSession)

  // Handle context from other pages
  useEffect(() => {
    if (context?.observation) {
      setInput(context.observation)
      clearContext()
    }
  }, [context, clearContext])

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, currentContent])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || isStreaming) return

    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: input.trim(),
      timestamp: new Date(),
    }

    setMessages((prev) => [...prev, userMessage])
    setInput('')
    setIsStreaming(true)
    setCurrentContent('')
    contentRef.current = ''
    setPhase('clarify')

    abortControllerRef.current = new AbortController()

    try {
      await agentApi.streamChat(
        {
          message: userMessage.content,
          user_id: 'demo_user',
          session_id: sessionId || undefined,
        },
        (event: StreamEvent) => {
          const data = JSON.parse(event.data)

          switch (event.event) {
            case 'session':
              if (data.session_id) {
                setSessionId(data.session_id)
                // Track session
                addSession({
                  source: 'deep_analysis',
                  label: userMessage.content.slice(0, 50),
                  backendSessionId: data.session_id,
                  preview: userMessage.content,
                })
              }
              break

            case 'phase':
              if (data.phase) {
                setPhase(data.phase as Phase)
              }
              break

            case 'token':
              if (data.content) {
                contentRef.current += data.content
                setCurrentContent(contentRef.current)
              }
              break

            case 'done':
              setPhase('complete')
              break

            case 'error':
              console.error('Stream error:', data.error)
              setPhase('idle')
              break
          }
        },
        abortControllerRef.current.signal
      )

      // Finalize assistant message using ref value (avoids stale closure)
      if (contentRef.current) {
        setMessages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: 'assistant',
            content: contentRef.current,
            timestamp: new Date(),
            phase: 'complete',
          },
        ])
      }
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        console.error('Chat error:', err)
        setMessages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: 'assistant',
            content: 'Sorry, an error occurred. Please try again.',
            timestamp: new Date(),
          },
        ])
      }
    } finally {
      setIsStreaming(false)
      setCurrentContent('')
      setPhase('idle')
    }
  }

  const handleNewChat = () => {
    setMessages([])
    setSessionId(null)
    setInput('')
    setCurrentContent('')
    setPhase('idle')
  }

  return (
    <div className="flex flex-col h-full" style={{ background: 'var(--bg-primary)' }}>
      {/* Header */}
      <header 
        className="flex items-center justify-between px-6 py-4 border-b"
        style={{ borderColor: 'var(--ui-border)' }}
      >
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate(-1)}
            className="p-2 rounded-lg hover:bg-white/5 transition-colors"
            style={{ color: 'var(--ui-text-secondary)' }}
          >
            <ChevronLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="font-semibold" style={{ color: 'var(--ui-text-primary)' }}>
              Deep Analysis
            </h1>
            {phase !== 'idle' && (
              <p className="text-sm" style={{ color: 'var(--accent-blue)' }}>
                {phaseDescriptions[phase]}
              </p>
            )}
          </div>
        </div>
        <button
          onClick={handleNewChat}
          className="px-4 py-2 rounded-lg text-sm font-medium transition-colors hover:bg-white/10"
          style={{ 
            border: '1px solid var(--ui-border)',
            color: 'var(--ui-text-secondary)'
          }}
        >
          New Analysis
        </button>
      </header>

      {/* Messages */}
      <div className="flex-1 overflow-auto p-6">
        <div className="max-w-3xl mx-auto space-y-6">
          {messages.length === 0 ? (
            <div className="text-center py-20">
              <MessageSquare 
                className="w-16 h-16 mx-auto mb-4" 
                style={{ color: 'var(--ui-text-muted)' }} 
              />
              <h2 
                className="text-xl font-semibold mb-2"
                style={{ color: 'var(--ui-text-primary)' }}
              >
                What would you like to know about your health?
              </h2>
              <p 
                className="max-w-md mx-auto"
                style={{ color: 'var(--ui-text-muted)' }}
              >
                Ask questions about your Apple Health data and get personalized, 
                AI-powered insights and analysis.
              </p>
              <div className="mt-8 flex flex-wrap justify-center gap-2">
                {[
                  'How has my sleep quality changed?',
                  'Analyze my heart rate variability',
                  'What affects my recovery scores?',
                ].map((suggestion) => (
                  <button
                    key={suggestion}
                    onClick={() => setInput(suggestion)}
                    className="px-4 py-2 rounded-lg text-sm transition-colors hover:bg-white/10"
                    style={{ 
                      border: '1px solid var(--ui-border)',
                      color: 'var(--ui-text-secondary)'
                    }}
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                    msg.role === 'user' ? 'rounded-br-sm' : 'rounded-bl-sm'
                  }`}
                  style={{
                    background: msg.role === 'user' 
                      ? 'linear-gradient(135deg, var(--accent-blue), var(--accent-purple))'
                      : 'var(--bg-card)',
                    color: msg.role === 'user' ? 'white' : 'var(--ui-text-primary)',
                    border: msg.role === 'assistant' ? '1px solid var(--ui-border)' : undefined,
                  }}
                >
                  <p className="whitespace-pre-wrap">{msg.content}</p>
                </div>
              </div>
            ))
          )}

          {/* Streaming content */}
          {isStreaming && currentContent && (
            <div className="flex justify-start">
              <div
                className="max-w-[80%] rounded-2xl rounded-bl-sm px-4 py-3"
                style={{
                  background: 'var(--bg-card)',
                  color: 'var(--ui-text-primary)',
                  border: '1px solid var(--ui-border)',
                }}
              >
                <p className="whitespace-pre-wrap">{currentContent}</p>
              </div>
            </div>
          )}

          {/* Streaming indicator */}
          {isStreaming && !currentContent && (
            <div className="flex justify-start">
              <div
                className="rounded-2xl rounded-bl-sm px-4 py-3 flex items-center gap-2"
                style={{
                  background: 'var(--bg-card)',
                  border: '1px solid var(--ui-border)',
                }}
              >
                <Loader2 className="w-4 h-4 animate-spin" style={{ color: 'var(--accent-blue)' }} />
                <span style={{ color: 'var(--ui-text-muted)' }}>
                  {phaseDescriptions[phase] || 'Thinking...'}
                </span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input */}
      <div 
        className="border-t p-4"
        style={{ borderColor: 'var(--ui-border)', background: 'var(--bg-secondary)' }}
      >
        <form onSubmit={handleSubmit} className="max-w-3xl mx-auto">
          <div 
            className="flex items-center gap-3 rounded-xl px-4 py-3"
            style={{ 
              background: 'var(--bg-card)',
              border: '1px solid var(--ui-border)'
            }}
          >
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about your health data..."
              disabled={isStreaming}
              className="flex-1 bg-transparent outline-none"
              style={{ color: 'var(--ui-text-primary)' }}
            />
            <button
              type="submit"
              disabled={!input.trim() || isStreaming}
              className="p-2 rounded-lg transition-colors disabled:opacity-50"
              style={{ 
                background: input.trim() && !isStreaming 
                  ? 'linear-gradient(135deg, var(--accent-blue), var(--accent-purple))'
                  : 'var(--ui-border)',
                color: 'white'
              }}
            >
              {isStreaming ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <Send className="w-5 h-5" />
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
