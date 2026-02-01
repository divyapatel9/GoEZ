/**
 * AI API service - calls /ai/* endpoints for chart explanations
 */

const API_BASE = '/ai'

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, options)
  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`)
  }
  return response.json()
}

// Types
export interface ChatRequest {
  user_id?: string
  chart_id: string
  message: string
  start_date: string
  end_date: string
  focus_date?: string
  metric_key?: string
}

export interface ChatResponse {
  answer: string
  evidence: string[]
  confidence: 'High' | 'Medium' | 'Low'
  confidence_reason: string
  next_questions: string[]
  context_summary: {
    chart_id: string
    date_range: { start: string; end: string }
    focus_date: string | null
    data_quality: {
      coverage_percent: number
      days_with_data: number
    }
    confidence_level: string
  }
  timestamp: string
}

export interface ThreadMessage {
  role: 'user' | 'assistant'
  content: string
  timestamp: string
  metadata?: Record<string, unknown>
}

export interface ThreadResponse {
  user_id: string
  chart_id: string
  messages: ThreadMessage[]
  count: number
}

export interface ChartInfo {
  chart_id: string
  display_name: string
  category: string
  quick_questions: string[]
}

export interface ChartsResponse {
  charts: ChartInfo[]
  count: number
}

// API Functions
export async function sendChatMessage(request: ChatRequest): Promise<ChatResponse> {
  return fetchJson<ChatResponse>(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      user_id: request.user_id || 'default_user',
      chart_id: request.chart_id,
      message: request.message,
      start_date: request.start_date,
      end_date: request.end_date,
      focus_date: request.focus_date,
      metric_key: request.metric_key,
    }),
  })
}

export async function getChatThread(
  chartId: string,
  userId: string = 'default_user'
): Promise<ThreadResponse> {
  const params = new URLSearchParams({ chart_id: chartId, user_id: userId })
  return fetchJson<ThreadResponse>(`${API_BASE}/chat/thread?${params}`)
}

export async function clearChatThread(
  chartId: string,
  userId: string = 'default_user'
): Promise<void> {
  const params = new URLSearchParams({ chart_id: chartId, user_id: userId })
  await fetch(`${API_BASE}/chat/thread?${params}`, { method: 'DELETE' })
}

export async function getAvailableCharts(): Promise<ChartsResponse> {
  return fetchJson<ChartsResponse>(`${API_BASE}/charts`)
}

export async function checkAIHealth(): Promise<{
  status: string
  api_key_configured: boolean
  charts_available: number
}> {
  return fetchJson(`${API_BASE}/health`)
}
