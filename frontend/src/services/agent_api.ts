/**
 * Agent API service - calls /agent/* endpoints for deep analysis
 */

const API_BASE = '/agent'

export interface ChatRequest {
  message: string
  user_id: string
  session_id?: string
  collection_name?: string
}

export interface StreamEvent {
  event: 'session' | 'phase' | 'token' | 'tasks' | 'subagent' | 'done' | 'error' | 'interrupt'
  data: string
}

export interface Session {
  session_id: string
  created_at?: string
  updated_at?: string
  preview?: string
}

export async function streamChat(
  request: ChatRequest,
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal
): Promise<void> {
  const response = await fetch(`${API_BASE}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
    signal,
  })

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`)
  }

  const reader = response.body?.getReader()
  if (!reader) throw new Error('No response body')

  const decoder = new TextDecoder()
  let buffer = ''
  let currentEventType: StreamEvent['event'] = 'token'

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('event:')) {
          currentEventType = line.slice(7).trim() as StreamEvent['event']
          continue
        }
        if (line.startsWith('data:')) {
          const data = line.slice(5).trim()
          if (data) {
            try {
              JSON.parse(data)
              onEvent({ event: currentEventType, data })
              currentEventType = 'token'
            } catch {
              // Skip malformed JSON
            }
          }
        }
      }
    }
  } finally {
    reader.releaseLock()
  }
}

export async function continueChat(
  request: ChatRequest,
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal
): Promise<void> {
  const response = await fetch(`${API_BASE}/chat/continue`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
    signal,
  })

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`)
  }

  const reader = response.body?.getReader()
  if (!reader) throw new Error('No response body')

  const decoder = new TextDecoder()
  let buffer = ''
  let currentEventType: StreamEvent['event'] = 'token'

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('event:')) {
          currentEventType = line.slice(7).trim() as StreamEvent['event']
          continue
        }
        if (line.startsWith('data:')) {
          const data = line.slice(5).trim()
          if (data) {
            try {
              JSON.parse(data)
              onEvent({ event: currentEventType, data })
              currentEventType = 'token'
            } catch {
              // Skip malformed JSON
            }
          }
        }
      }
    }
  } finally {
    reader.releaseLock()
  }
}

export async function getUserSessions(userId: string): Promise<{ sessions: Session[] }> {
  const response = await fetch(`${API_BASE}/sessions/${userId}`)
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
  return response.json()
}

export async function getSessionHistory(userId: string, sessionId: string): Promise<{
  session_id: string
  messages: Array<{ role: 'user' | 'assistant'; content: string }>
}> {
  const response = await fetch(`${API_BASE}/sessions/${userId}/${sessionId}/history`)
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
  return response.json()
}

export async function deleteSession(userId: string, sessionId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/sessions/${userId}/${sessionId}`, { method: 'DELETE' })
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
}

export async function checkHealth(): Promise<{ status: string; version: string }> {
  const response = await fetch(`${API_BASE}/health`)
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
  return response.json()
}
