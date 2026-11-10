const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? ''

export type State = {
  today: string; reportedToday: boolean; answeredToday: boolean; approvedToday: boolean
  streak: number; selfStreak: number; points: number; stage: number; stageName: string
  dayNo: number; totalDays: number; nextStageDays: number | null
  inventory: Record<string, number>; itemToday: string | null; daysToNextItem: number; sabori: boolean
  sparkly: boolean
  bloom: boolean
  demoMode: boolean
  family: { childNickname: string; buddyName: string; ageBand: string; demo: boolean; gender: 'boy' | 'girl' }
}
export type Question = { id: string; axis: string; text: string; choices: string[] }
export type Approval = { canApprove: boolean; alreadyApproved: boolean; facts: string[]; trend: string | null; trendSource: string | null }
export type PhraseHint = { phrases: string[]; source: string | null }
export type Weekly = {
  weekId: string; weekStart: string; doneDays: number; selfDays: number; longestStreak: number
  prevDoneDays: number | null; prevSelfDays: number | null; answerCount: number
  trendAvailable: boolean; trendText: string | null
}

export const store = {
  get fid() { try { return localStorage.getItem('fid') } catch { return null } },
  set fid(v: string | null) { try { v ? localStorage.setItem('fid', v) : localStorage.removeItem('fid') } catch { /* noop */ } },
}

// デモ用の仮の日時（DEMO_MODE=1 のサーバーでだけ効く）。パネルで操作し、全APIに X-Debug-Now として付ける
export const demoClock = {
  enabled: false, // サーバーが demoMode=true と返した時だけ true（App が設定）。本番では常に false
  // 画面表示用の「いま」。デモモードで仮の日時があるときだけ仮の日時、それ以外は本物の現在時刻
  effectiveNow(): Date { const n = this.enabled ? this.now : null; const d = n ? new Date(n) : null; return d && !isNaN(+d) ? d : new Date() },
  get now(): string | null { try { return localStorage.getItem('debugNow') } catch { return null } },
  set now(v: string | null) { try { v ? localStorage.setItem('debugNow', v) : localStorage.removeItem('debugNow') } catch { /* noop */ } },
}

async function call<T>(method: string, path: string, body?: unknown, pin?: string): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (store.fid) headers['X-Family-Id'] = store.fid
  if (pin) headers['X-Parent-Pin'] = pin
  const dbg = demoClock.now ?? new URLSearchParams(location.search).get('now') // ?now=2026-11-10T10:00:00%2B09:00 でも指定できる
  if (dbg) headers['X-Debug-Now'] = dbg
  if (new URLSearchParams(location.search).get('demo')) headers['X-Demo'] = '1'
  const r = await fetch(BASE + path, { method, headers, body: body ? JSON.stringify(body) : undefined })
  const j = await r.json().catch(() => ({}))
  if (!r.ok) throw Object.assign(new Error(j.detail ?? 'error'), { status: r.status })
  return j as T
}

export const api = {
  createFamily: (b: { childNickname: string; ageBand: string; buddyName: string; pin: string; gender: string }) =>
    call<{ familyId: string }>('POST', '/api/families', b),
  state: () => call<State>('GET', '/api/state'),
  report: (selfStarted: boolean) => call<State>('POST', '/api/report', { selfStarted }),
  questions: () => call<{ questions: Question[] }>('GET', '/api/questions'),
  answers: (answers: { axis: string; choice: number }[]) =>
    call<{ pointsGained: number; state: State }>('POST', '/api/answers', { answers }),
  giveItem: (key: string) => call<State>('POST', '/api/items/give', { key }),
  verify: (pin: string) => call('POST', '/api/parent/verify', { pin }),
  approval: (pin: string) => call<Approval>('GET', '/api/parent/approval', undefined, pin),
  phraseHint: (pin: string) => call<PhraseHint>('GET', '/api/parent/phrase-hint', undefined, pin),
  approve: (pin: string, phrase: string, edited: boolean, watched: boolean) =>
    call<{ state: State; itemGot: string | null }>('POST', '/api/parent/approve', { phrase, edited, watched }, pin),
  weekly: (pin: string) => call<Weekly>('GET', '/api/parent/weekly', undefined, pin),
  deleteFamily: (pin: string) => call('DELETE', '/api/family', undefined, pin),
}
