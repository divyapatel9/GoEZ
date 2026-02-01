/**
 * AI Dock - Main container for AI chat interface.
 * 
 * Features:
 * - Minimizable/expandable dock panel
 * - Chart scope selector
 * - Chat thread with messages
 * - Quick question chips
 * - Confidence indicators
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { Sparkles, X, Minimize2, Maximize2, Send, Trash2, ChevronDown } from 'lucide-react';
import { colors } from '@/styles/theme';
import {
  sendChatMessage,
  getChatThread,
  clearChatThread,
  getAvailableCharts,
  type ChatResponse,
  type ThreadMessage,
  type ChartInfo,
} from '@/services/ai_api';
import { getDateRangeFromPreset } from './CardTimeSelector';

// =============================================================================
// SUB-COMPONENTS
// =============================================================================

interface ConfidenceBadgeProps {
  level: 'High' | 'Medium' | 'Low';
  reason?: string;
}

function ConfidenceBadge({ level, reason }: ConfidenceBadgeProps) {
  const colorMap = {
    High: colors.state.good,
    Medium: colors.state.warning,
    Low: colors.state.danger,
  };
  
  return (
    <div
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium"
      style={{
        background: `${colorMap[level]}20`,
        color: colorMap[level],
        border: `1px solid ${colorMap[level]}40`,
      }}
      title={reason}
    >
      <span
        className="w-1.5 h-1.5 rounded-full"
        style={{ background: colorMap[level] }}
      />
      {level} Confidence
    </div>
  );
}

interface QuickChipsProps {
  questions: string[];
  onSelect: (question: string) => void;
  disabled?: boolean;
}

function QuickChips({ questions, onSelect, disabled }: QuickChipsProps) {
  if (!questions.length) return null;
  
  return (
    <div className="flex flex-wrap gap-2">
      {questions.map((q, i) => (
        <button
          key={i}
          onClick={() => onSelect(q)}
          disabled={disabled}
          className="px-3 py-1.5 text-xs rounded-full transition-all hover:scale-105"
          style={{
            background: colors.bg.glass,
            border: `1px solid ${colors.ui.border}`,
            color: colors.ui.text.secondary,
            opacity: disabled ? 0.5 : 1,
            cursor: disabled ? 'not-allowed' : 'pointer',
          }}
        >
          {q}
        </button>
      ))}
    </div>
  );
}

interface EvidenceListProps {
  evidence: string[];
}

function EvidenceList({ evidence }: EvidenceListProps) {
  const [expanded, setExpanded] = useState(false);
  
  if (!evidence.length) return null;
  
  return (
    <div className="mt-2">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1 text-xs transition-colors"
        style={{ color: colors.ui.text.muted }}
      >
        <ChevronDown
          size={12}
          style={{
            transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
            transition: 'transform 0.2s',
          }}
        />
        {expanded ? 'Hide' : 'Show'} evidence ({evidence.length})
      </button>
      
      {expanded && (
        <ul className="mt-2 space-y-1 text-xs" style={{ color: colors.ui.text.muted }}>
          {evidence.map((e, i) => (
            <li key={i} className="flex items-start gap-2">
              <span style={{ color: colors.ui.accent }}>•</span>
              <span>{e}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

interface MessageBubbleProps {
  message: ThreadMessage;
  response?: ChatResponse;
}

function MessageBubble({ message, response }: MessageBubbleProps) {
  const isUser = message.role === 'user';
  
  return (
    <div
      className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}
    >
      <div
        className="max-w-[85%] rounded-2xl px-4 py-3"
        style={{
          background: isUser ? colors.ui.accent : colors.bg.card,
          border: isUser ? 'none' : `1px solid ${colors.ui.border}`,
        }}
      >
        <p
          className="text-sm whitespace-pre-wrap"
          style={{ color: colors.ui.text.primary }}
        >
          {message.content}
        </p>
        
        {!isUser && response && (
          <>
            <div className="mt-2 flex items-center gap-2">
              <ConfidenceBadge
                level={response.confidence}
                reason={response.confidence_reason}
              />
            </div>
            <EvidenceList evidence={response.evidence} />
          </>
        )}
      </div>
    </div>
  );
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

interface AIDockProps {
  isOpen: boolean;
  onClose: () => void;
  activeChartId?: string;
}

export function AIDock({ isOpen, onClose, activeChartId }: AIDockProps) {
  const [minimized, setMinimized] = useState(false);
  const [chartId, setChartId] = useState(activeChartId || 'recovery_gauge');
  const [charts, setCharts] = useState<ChartInfo[]>([]);
  const [messages, setMessages] = useState<ThreadMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [lastResponse, setLastResponse] = useState<ChatResponse | null>(null);
  const [quickQuestions, setQuickQuestions] = useState<string[]>([]);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  
  // Load available charts
  useEffect(() => {
    getAvailableCharts()
      .then((res) => {
        setCharts(res.charts);
        // Set quick questions for current chart
        const current = res.charts.find((c) => c.chart_id === chartId);
        if (current) {
          setQuickQuestions(current.quick_questions);
        }
      })
      .catch(console.error);
  }, []);
  
  // Update chart when activeChartId changes
  useEffect(() => {
    if (activeChartId && activeChartId !== chartId) {
      setChartId(activeChartId);
    }
  }, [activeChartId]);
  
  // Load chat thread when chart changes
  useEffect(() => {
    getChatThread(chartId)
      .then((res) => {
        setMessages(res.messages);
      })
      .catch(console.error);
    
    // Update quick questions
    const current = charts.find((c) => c.chart_id === chartId);
    if (current) {
      setQuickQuestions(current.quick_questions);
    }
  }, [chartId, charts]);
  
  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);
  
  // Focus input when dock opens
  useEffect(() => {
    if (isOpen && !minimized) {
      inputRef.current?.focus();
    }
  }, [isOpen, minimized]);
  
  const handleSend = useCallback(async (messageText?: string) => {
    const text = messageText || input.trim();
    if (!text || isLoading) return;
    
    setInput('');
    setIsLoading(true);
    
    // Add user message optimistically
    const userMessage: ThreadMessage = {
      role: 'user',
      content: text,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMessage]);
    
    try {
      // Get date range (default to 30 days)
      const { start, end } = getDateRangeFromPreset('30d');
      
      const response = await sendChatMessage({
        chart_id: chartId,
        message: text,
        start_date: start,
        end_date: end,
      });
      
      // Add assistant message
      const assistantMessage: ThreadMessage = {
        role: 'assistant',
        content: response.answer,
        timestamp: response.timestamp,
      };
      setMessages((prev) => [...prev, assistantMessage]);
      setLastResponse(response);
      
      // Update quick questions with suggested follow-ups
      if (response.next_questions.length > 0) {
        setQuickQuestions(response.next_questions);
      }
    } catch (error) {
      console.error('Chat error:', error);
      // Add error message
      const errorMessage: ThreadMessage = {
        role: 'assistant',
        content: 'Sorry, I encountered an error processing your message. Please try again.',
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  }, [input, chartId, isLoading]);
  
  const handleClearThread = useCallback(async () => {
    try {
      await clearChatThread(chartId);
      setMessages([]);
      setLastResponse(null);
      
      // Reset quick questions
      const current = charts.find((c) => c.chart_id === chartId);
      if (current) {
        setQuickQuestions(current.quick_questions);
      }
    } catch (error) {
      console.error('Clear thread error:', error);
    }
  }, [chartId, charts]);
  
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };
  
  if (!isOpen) return null;
  
  const currentChart = charts.find((c) => c.chart_id === chartId);
  
  return (
    <div
      className="fixed bottom-4 right-4 z-50 flex flex-col rounded-2xl overflow-hidden shadow-2xl"
      style={{
        width: minimized ? '280px' : '400px',
        height: minimized ? '56px' : '600px',
        background: colors.bg.primary,
        border: `1px solid ${colors.ui.border}`,
        transition: 'all 0.3s ease',
      }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-3 shrink-0"
        style={{
          background: colors.bg.card,
          borderBottom: `1px solid ${colors.ui.border}`,
        }}
      >
        <div className="flex items-center gap-2">
          <Sparkles size={18} style={{ color: colors.ui.accent }} />
          <span className="font-semibold text-sm" style={{ color: colors.ui.text.primary }}>
            AI Coach
          </span>
          {!minimized && currentChart && (
            <span
              className="text-xs px-2 py-0.5 rounded"
              style={{
                background: colors.bg.glass,
                color: colors.ui.text.muted,
              }}
            >
              {currentChart.display_name}
            </span>
          )}
        </div>
        
        <div className="flex items-center gap-1">
          {!minimized && messages.length > 0 && (
            <button
              onClick={handleClearThread}
              className="p-1.5 rounded-lg transition-colors hover:bg-white/10"
              title="Clear conversation"
            >
              <Trash2 size={14} style={{ color: colors.ui.text.muted }} />
            </button>
          )}
          <button
            onClick={() => setMinimized(!minimized)}
            className="p-1.5 rounded-lg transition-colors hover:bg-white/10"
          >
            {minimized ? (
              <Maximize2 size={14} style={{ color: colors.ui.text.muted }} />
            ) : (
              <Minimize2 size={14} style={{ color: colors.ui.text.muted }} />
            )}
          </button>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg transition-colors hover:bg-white/10"
          >
            <X size={14} style={{ color: colors.ui.text.muted }} />
          </button>
        </div>
      </div>
      
      {!minimized && (
        <>
          {/* Chart Selector */}
          <div
            className="px-4 py-2 shrink-0"
            style={{ borderBottom: `1px solid ${colors.ui.border}` }}
          >
            <select
              value={chartId}
              onChange={(e) => setChartId(e.target.value)}
              className="w-full px-3 py-2 rounded-lg text-sm"
              style={{
                background: '#2a2a3a',
                border: `1px solid ${colors.ui.border}`,
                color: '#ffffff',
                outline: 'none',
              }}
            >
              {charts.map((chart) => (
                <option
                  key={chart.chart_id}
                  value={chart.chart_id}
                  style={{ background: '#2a2a3a', color: '#ffffff' }}
                >
                  {chart.display_name}
                </option>
              ))}
            </select>
          </div>
          
          {/* Messages */}
          <div
            className="flex-1 overflow-y-auto p-4 space-y-4"
            style={{ minHeight: 0 }}
          >
            {messages.length === 0 ? (
              <div className="text-center py-8">
                <Sparkles
                  size={32}
                  className="mx-auto mb-3"
                  style={{ color: colors.ui.accent, opacity: 0.5 }}
                />
                <p
                  className="text-sm mb-4"
                  style={{ color: colors.ui.text.muted }}
                >
                  Ask me about your {currentChart?.display_name || 'health data'}
                </p>
                <QuickChips
                  questions={quickQuestions}
                  onSelect={handleSend}
                  disabled={isLoading}
                />
              </div>
            ) : (
              <>
                {messages.map((msg, i) => (
                  <MessageBubble
                    key={i}
                    message={msg}
                    response={
                      msg.role === 'assistant' && i === messages.length - 1
                        ? lastResponse || undefined
                        : undefined
                    }
                  />
                ))}
                
                {isLoading && (
                  <div className="flex justify-start">
                    <div
                      className="px-4 py-3 rounded-2xl"
                      style={{
                        background: colors.bg.card,
                        border: `1px solid ${colors.ui.border}`,
                      }}
                    >
                      <div className="flex items-center gap-2">
                        <div className="flex gap-1">
                          {[0, 1, 2].map((i) => (
                            <div
                              key={i}
                              className="w-2 h-2 rounded-full animate-bounce"
                              style={{
                                background: colors.ui.accent,
                                animationDelay: `${i * 0.15}s`,
                              }}
                            />
                          ))}
                        </div>
                        <span
                          className="text-xs"
                          style={{ color: colors.ui.text.muted }}
                        >
                          Analyzing your data...
                        </span>
                      </div>
                    </div>
                  </div>
                )}
                
                <div ref={messagesEndRef} />
              </>
            )}
          </div>
          
          {/* Quick Questions (when there are messages) */}
          {messages.length > 0 && quickQuestions.length > 0 && (
            <div
              className="px-4 py-2 shrink-0"
              style={{ borderTop: `1px solid ${colors.ui.border}` }}
            >
              <QuickChips
                questions={quickQuestions}
                onSelect={handleSend}
                disabled={isLoading}
              />
            </div>
          )}
          
          {/* Input */}
          <div
            className="px-4 py-3 shrink-0"
            style={{
              background: colors.bg.card,
              borderTop: `1px solid ${colors.ui.border}`,
            }}
          >
            <div
              className="flex items-center gap-2 px-3 py-2 rounded-xl"
              style={{
                background: colors.bg.glass,
                border: `1px solid ${colors.ui.border}`,
              }}
            >
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask about your health data..."
                disabled={isLoading}
                className="flex-1 bg-transparent text-sm outline-none"
                style={{ color: colors.ui.text.primary }}
              />
              <button
                onClick={() => handleSend()}
                disabled={!input.trim() || isLoading}
                className="p-2 rounded-lg transition-all"
                style={{
                  background: input.trim() ? colors.ui.accent : 'transparent',
                  opacity: input.trim() && !isLoading ? 1 : 0.5,
                  cursor: input.trim() && !isLoading ? 'pointer' : 'not-allowed',
                }}
              >
                <Send size={16} style={{ color: colors.ui.text.primary }} />
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

// =============================================================================
// SPARKLE BUTTON
// =============================================================================

interface SparkleButtonProps {
  onClick: () => void;
  isOpen: boolean;
}

export function SparkleButton({ onClick, isOpen }: SparkleButtonProps) {
  if (isOpen) return null;
  
  return (
    <button
      onClick={onClick}
      className="fixed bottom-4 right-4 z-50 p-4 rounded-full shadow-lg transition-all hover:scale-110"
      style={{
        background: `linear-gradient(135deg, ${colors.ui.accent} 0%, #8b5cf6 100%)`,
        boxShadow: `0 4px 20px ${colors.ui.accentGlow}`,
      }}
    >
      <Sparkles size={24} style={{ color: '#ffffff' }} />
    </button>
  );
}
