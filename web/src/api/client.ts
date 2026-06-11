import type {
  PlanRequest, PlanResponse,
  DebriefRequest, DebriefResponse,
  DetectResponse,
  CueOptionsResponse,
  TableState, IntentionIn,
} from '../types/pillars'

const BASE = '/api'

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  return res.json()
}

export async function fetchPlan(req: PlanRequest): Promise<PlanResponse> {
  return post('/plan', req)
}

export async function fetchDebrief(req: DebriefRequest): Promise<DebriefResponse> {
  return post('/debrief', req)
}

export async function fetchDetect(imageFile: File): Promise<DetectResponse> {
  const form = new FormData()
  form.append('image', imageFile)
  const res = await fetch(`${BASE}/detect`, { method: 'POST', body: form })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  return res.json()
}

export async function fetchCueOptions(body: {
  state: TableState
  intention: IntentionIn
  target_position_m: [number, number]
  tolerance_m?: number
  max_options?: number
}): Promise<CueOptionsResponse> {
  return post('/cue-options', body)
}

export async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${BASE}/health`)
    return res.ok
  } catch {
    return false
  }
}
