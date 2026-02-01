/**
 * Deep Analysis Module
 * 
 * Migrated from health-hackathon-PANW/frontend - Agent Chat Interface
 * This module provides AI-powered deep health analysis via /agent/* endpoints
 */

import { useState, useEffect, useRef } from 'react'
import { Send, Loader2, MessageSquare, ChevronLeft, ChevronDown, ChevronRight, Brain, ListChecks, Search, HelpCircle } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import { agentApi } from '@/services'
import { useContextStore } from '@/store/contextStore'
import { useSessionStore } from '@/store/sessionStore'
import type { StreamEvent } from '@/services/agent_api'

interface PhaseContent {
  clarify: string
  planning: string
  analyzing: string
}

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  phase?: string
  phaseData?: PhaseContent
}

type Phase = 'idle' | 'clarify' | 'planning' | 'analyzing' | 'writing' | 'complete' | 'awaiting_clarification'

const phaseDescriptions: Record<Phase, string> = {
  idle: '',
  clarify: 'Understanding your question...',
  planning: 'Planning analysis approach...',
  analyzing: 'Analyzing health data...',
  writing: 'Generating insights...',
  complete: 'Analysis complete',
  awaiting_clarification: 'Waiting for your response...',
}

function stripCodeFences(content: string): string {
  let result = content
  // Remove opening code fence with optional language (e.g., ```markdown, ```)
  result = result.replace(/^```(?:markdown|md)?\s*\n?/i, '')
  // Remove closing code fence
  result = result.replace(/\n?```\s*$/i, '')
  return result.trim()
}

const phaseIcons: Record<string, React.ReactNode> = {
  clarify: <Brain className="w-4 h-4" />,
  planning: <ListChecks className="w-4 h-4" />,
  analyzing: <Search className="w-4 h-4" />,
}

const phaseTitles: Record<string, string> = {
  clarify: 'Understanding',
  planning: 'Planning',
  analyzing: 'Analyzing',
}

function PhaseSection({ 
  phase, 
  content, 
  isActive,
  isComplete 
}: { 
  phase: string
  content: string
  isActive: boolean
  isComplete: boolean
}) {
  const [isExpanded, setIsExpanded] = useState(false)
  
  // Auto-expand when active
  useEffect(() => {
    if (isActive) setIsExpanded(true)
  }, [isActive])
  
  if (!content && !isActive) return null
  
  return (
    <div 
      className="rounded-lg overflow-hidden mb-2"
      style={{ 
        background: 'var(--bg-secondary)',
        border: '1px solid var(--ui-border)'
      }}
    >
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-white/5 transition-colors"
      >
        <span style={{ color: isActive ? 'var(--accent-blue)' : 'var(--ui-text-muted)' }}>
          {phaseIcons[phase]}
        </span>
        <span 
          className="flex-1 text-sm font-medium"
          style={{ color: isActive ? 'var(--accent-blue)' : 'var(--ui-text-secondary)' }}
        >
          {phaseTitles[phase]}
        </span>
        {isActive && !isComplete && (
          <Loader2 className="w-3 h-3 animate-spin" style={{ color: 'var(--accent-blue)' }} />
        )}
        {isComplete && (
          <span className="text-xs px-1.5 py-0.5 rounded" style={{ background: 'var(--accent-green)', color: 'white' }}>Done</span>
        )}
        <span style={{ color: 'var(--ui-text-muted)' }}>
          {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
        </span>
      </button>
      {isExpanded && (
        <div 
          className="px-3 py-2 text-xs font-mono overflow-auto max-h-40"
          style={{ 
            borderTop: '1px solid var(--ui-border)',
            color: 'var(--ui-text-muted)',
            background: 'var(--bg-primary)'
          }}
        >
          <pre className="whitespace-pre-wrap break-words">
            {content || 'Processing...'}
          </pre>
        </div>
      )}
    </div>
  )
}

export function DeepAnalysis() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [phase, setPhase] = useState<Phase>('idle')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [currentContent, setCurrentContent] = useState('')
  const [phaseContent, setPhaseContent] = useState<PhaseContent>({
    clarify: '',
    planning: '',
    analyzing: '',
  })
  const [completedPhases, setCompletedPhases] = useState<Set<string>>(new Set())
  const [clarificationInput, setClarificationInput] = useState('')
  const [awaitingClarification, setAwaitingClarification] = useState(false)
  
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const messagesContainerRef = useRef<HTMLDivElement>(null)
  const userScrolledRef = useRef(false)
  const abortControllerRef = useRef<AbortController | null>(null)
  const contentRef = useRef<string>('')
  const phaseContentRef = useRef<PhaseContent>({
    clarify: '',
    planning: '',
    analyzing: '',
  })
  
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

  // Handle user scroll detection
  const handleScroll = () => {
    const container = messagesContainerRef.current
    if (!container) return
    
    // Check if user is near bottom (within 100px)
    const isNearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 100
    userScrolledRef.current = !isNearBottom
  }

  // Auto-scroll to bottom only if user hasn't scrolled up
  useEffect(() => {
    if (!userScrolledRef.current) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, currentContent])

  // Reset scroll flag when new message is sent
  useEffect(() => {
    if (isStreaming) {
      userScrolledRef.current = false
    }
  }, [isStreaming])

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
    setPhaseContent({ clarify: '', planning: '', analyzing: '' })
    phaseContentRef.current = { clarify: '', planning: '', analyzing: '' }
    setCompletedPhases(new Set())

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
                // Mark previous phase as complete
                const prevPhase = phase
                if (prevPhase && prevPhase !== 'idle' && prevPhase !== data.phase) {
                  setCompletedPhases(prev => new Set([...prev, prevPhase]))
                }
                setPhase(data.phase as Phase)
              }
              break

            case 'token':
              if (data.content) {
                const tokenPhase = data.phase as string
                // Route to appropriate phase content
                if (tokenPhase === 'writing') {
                  contentRef.current += data.content
                  setCurrentContent(contentRef.current)
                } else if (tokenPhase === 'clarify' || tokenPhase === 'planning' || tokenPhase === 'analyzing') {
                  phaseContentRef.current[tokenPhase] += data.content
                  setPhaseContent({ ...phaseContentRef.current })
                }
              }
              break

            case 'interrupt':
              // Agent is asking for clarification
              if (data.reason === 'clarification_needed') {
                setAwaitingClarification(true)
                setPhase('awaiting_clarification')
                setIsStreaming(false)
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
        const finalPhaseData = { ...phaseContentRef.current }
        setMessages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: 'assistant',
            content: contentRef.current,
            timestamp: new Date(),
            phase: 'complete',
            phaseData: finalPhaseData,
          },
        ])
        // Reset phase content after storing in message
        setPhaseContent({ clarify: '', planning: '', analyzing: '' })
        phaseContentRef.current = { clarify: '', planning: '', analyzing: '' }
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

  const handleClarificationSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!clarificationInput.trim() || !sessionId || isStreaming) return

    const userResponse = clarificationInput.trim()
    setClarificationInput('')
    setAwaitingClarification(false)
    setIsStreaming(true)
    setPhase('clarify')
    // Keep existing phase content, just continue from where we left off

    abortControllerRef.current = new AbortController()

    try {
      await agentApi.continueChat(
        {
          message: userResponse,
          user_id: 'demo_user',
          session_id: sessionId,
        },
        (event: StreamEvent) => {
          const data = JSON.parse(event.data)

          switch (event.event) {
            case 'phase':
              if (data.phase) {
                const prevPhase = phase
                if (prevPhase && prevPhase !== 'idle' && prevPhase !== 'awaiting_clarification' && prevPhase !== data.phase) {
                  setCompletedPhases(prev => new Set([...prev, prevPhase]))
                }
                setPhase(data.phase as Phase)
              }
              break

            case 'token':
              if (data.content) {
                const tokenPhase = data.phase as string
                if (tokenPhase === 'writing') {
                  contentRef.current += data.content
                  setCurrentContent(contentRef.current)
                } else if (tokenPhase === 'clarify' || tokenPhase === 'planning' || tokenPhase === 'analyzing') {
                  phaseContentRef.current[tokenPhase] += data.content
                  setPhaseContent({ ...phaseContentRef.current })
                }
              }
              break

            case 'interrupt':
              if (data.reason === 'clarification_needed') {
                setAwaitingClarification(true)
                setPhase('awaiting_clarification')
                setIsStreaming(false)
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

      if (contentRef.current) {
        const finalPhaseData = { ...phaseContentRef.current }
        setMessages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: 'assistant',
            content: contentRef.current,
            timestamp: new Date(),
            phase: 'complete',
            phaseData: finalPhaseData,
          },
        ])
        // Reset phase content after storing in message
        setPhaseContent({ clarify: '', planning: '', analyzing: '' })
        phaseContentRef.current = { clarify: '', planning: '', analyzing: '' }
      }
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        console.error('Continue chat error:', err)
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
    setPhaseContent({ clarify: '', planning: '', analyzing: '' })
    phaseContentRef.current = { clarify: '', planning: '', analyzing: '' }
    setCompletedPhases(new Set())
    setClarificationInput('')
    setAwaitingClarification(false)
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
      <div 
        ref={messagesContainerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-auto p-6"
      >
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
                  {msg.role === 'user' ? (
                    <p className="whitespace-pre-wrap">{msg.content}</p>
                  ) : (
                    <>
                      {/* Show phase sections above report content for completed messages */}
                      {msg.phaseData && (msg.phaseData.clarify || msg.phaseData.planning || msg.phaseData.analyzing) && (
                        <div className="mb-3">
                          {(['clarify', 'planning', 'analyzing'] as const).map((p) => (
                            msg.phaseData && msg.phaseData[p] ? (
                              <PhaseSection
                                key={p}
                                phase={p}
                                content={msg.phaseData[p]}
                                isActive={false}
                                isComplete={true}
                              />
                            ) : null
                          ))}
                        </div>
                      )}
                      <div className="markdown-content">
                        <ReactMarkdown>{stripCodeFences(msg.content)}</ReactMarkdown>
                      </div>
                    </>
                  )}
                </div>
              </div>
            ))
          )}

          {/* Collapsible phase sections - shown during streaming or awaiting clarification */}
          {(isStreaming || awaitingClarification) && (
            <div className="flex justify-start">
              <div
                className="w-full max-w-[80%] rounded-2xl rounded-bl-sm px-4 py-3"
                style={{
                  background: 'var(--bg-card)',
                  border: '1px solid var(--ui-border)',
                }}
              >
                {(['clarify', 'planning', 'analyzing'] as const).map((p) => (
                  <PhaseSection
                    key={p}
                    phase={p}
                    content={phaseContent[p]}
                    isActive={phase === p || (p === 'clarify' && awaitingClarification)}
                    isComplete={completedPhases.has(p) || 
                      (['planning', 'analyzing', 'writing', 'complete'].includes(phase) && p === 'clarify' && !awaitingClarification) ||
                      (['analyzing', 'writing', 'complete'].includes(phase) && p === 'planning') ||
                      (['writing', 'complete'].includes(phase) && p === 'analyzing')}
                  />
                ))}

                {/* Clarification request UI */}
                {awaitingClarification && (
                  <div 
                    className="mt-3 rounded-lg p-3"
                    style={{ 
                      background: 'linear-gradient(135deg, rgba(59, 130, 246, 0.1), rgba(139, 92, 246, 0.1))',
                      border: '1px solid var(--accent-blue)'
                    }}
                  >
                    <div className="flex items-center gap-2 mb-2">
                      <HelpCircle className="w-4 h-4" style={{ color: 'var(--accent-blue)' }} />
                      <span className="text-sm font-medium" style={{ color: 'var(--accent-blue)' }}>
                        Clarification Needed
                      </span>
                    </div>
                    <div 
                      className="text-sm mb-3 markdown-content"
                      style={{ color: 'var(--ui-text-primary)' }}
                    >
                      <ReactMarkdown>{phaseContent.clarify.split('\n').slice(-5).join('\n')}</ReactMarkdown>
                    </div>
                    <form onSubmit={handleClarificationSubmit} className="flex gap-2">
                      <input
                        type="text"
                        value={clarificationInput}
                        onChange={(e) => setClarificationInput(e.target.value)}
                        placeholder="Type your response..."
                        autoFocus
                        className="flex-1 px-3 py-2 rounded-lg text-sm bg-transparent outline-none"
                        style={{ 
                          border: '1px solid var(--ui-border)',
                          color: 'var(--ui-text-primary)'
                        }}
                      />
                      <button
                        type="submit"
                        disabled={!clarificationInput.trim()}
                        className="px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
                        style={{ 
                          background: clarificationInput.trim() 
                            ? 'linear-gradient(135deg, var(--accent-blue), var(--accent-purple))'
                            : 'var(--ui-border)',
                          color: 'white'
                        }}
                      >
                        <Send className="w-4 h-4" />
                      </button>
                    </form>
                  </div>
                )}
                
                {/* Writing phase indicator */}
                {phase === 'writing' && !currentContent && (
                  <div className="flex items-center gap-2 mt-2">
                    <Loader2 className="w-4 h-4 animate-spin" style={{ color: 'var(--accent-blue)' }} />
                    <span className="text-sm" style={{ color: 'var(--ui-text-muted)' }}>
                      Generating report...
                    </span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Streaming content - now BELOW the phase sections */}
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
                <div className="markdown-content">
                  <ReactMarkdown>{stripCodeFences(currentContent)}</ReactMarkdown>
                </div>
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
              placeholder={awaitingClarification ? "Please respond above..." : "Ask about your health data..."}
              disabled={isStreaming || awaitingClarification}
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
