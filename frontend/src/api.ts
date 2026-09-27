// Client for server.py. Set VITE_API_URL when the API runs on another host (e.g. Colab + ngrok).
const BASE = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') ?? ''

export type ToolStatus = 'ok' | 'needs_key' | 'unavailable'
export interface ToolInfo { name: string; description: string; status: ToolStatus }
export interface Health { mode: 'demo' | 'agent'; model: string | null; tools: ToolInfo[]; warning?: string | null }

export interface Machine {
  model: string; category: string; hp: number; price_inr: number; stock: number; fuel_lph: number; notes: string
}
export interface Part { part_no: string; name: string; model: string; price_inr: number; stock: number }

export interface AdviceCard {
  recommendation: string
  key_figures: string[]
  tools_used: string[]
  data_gaps: string
  confidence: 'high' | 'medium' | 'low'
}

export type StreamEvent =
  | { type: 'thinking' }
  | { type: 'tool_start'; id: string; tool: string; input: unknown }
  | { type: 'tool_end'; id: string; output: string; error: boolean }
  | { type: 'final'; answer: string; card: AdviceCard; latency_ms: number }
  | { type: 'error'; message: string }

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

export const getHealth = () => getJSON<Health>('/api/health')
export const getInventory = () => getJSON<{ machines: Machine[]; parts: Part[] }>('/api/inventory')

/** POST a question and call onEvent for each NDJSON line as the agent works. */
export async function streamChat(
  message: string,
  sessionId: string,
  onEvent: (e: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${BASE}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId }),
    signal,
  })
  if (!res.ok || !res.body) throw new Error(`Server returned ${res.status}`)
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let nl: number
    while ((nl = buffer.indexOf('\n')) >= 0) {
      const line = buffer.slice(0, nl).trim()
      buffer = buffer.slice(nl + 1)
      if (line) onEvent(JSON.parse(line) as StreamEvent)
    }
  }
  if (buffer.trim()) onEvent(JSON.parse(buffer) as StreamEvent)
}

/** 850000 -> "8,50,000" */
export const inr = (n: number) => new Intl.NumberFormat('en-IN').format(n)
