import { useEffect, useRef, useState } from 'react'
import { api, type Approval, type Question, type State, type Weekly } from './api'
import { Buddy, Demon, ItemArt, Mat, NavIcon, StartBuddy, SunWindow } from './art'
import { BUDDY_NAME, ITEMS, ITEM_COLOR, ITEM_LINES, ITEM_ORDER, S, suffix } from './strings'

const speak = (t: string) => {
  try { const u = new SpeechSynthesisUtterance(t); u.lang = 'ja-JP'; speechSynthesis.cancel(); speechSynthesis.speak(u) } catch { /* noop */ }
}
const Demo = ({ s }: { s: State | null }) => (s?.family.demo ? <span className="badge">{S.demoBadge}</span> : null)

// ---------- スタート ----------
export function Start({ onTap }: { onTap: () => void }) {
  return (
    <div className="phone deep start" onClick={onTap} role="button">
      <div className="blob"><div className="lead">ねぇ、</div><div className="big">できた</div></div>
      <div className="buddy-wrap"><StartBuddy /></div>
      <div className="tap">{S.tapStart}</div>
    </div>
  )
}

// ---------- 初期設定（おとな向け） ----------
type SetupIn = { childNickname: string; ageBand: string; buddyName: string; pin: string; gender: string }
export function Setup({ onDone }: { onDone: (b: SetupIn) => Promise<void> }) {
  const [f, setF] = useState<SetupIn>({ childNickname: '', ageBand: '5-6', buddyName: BUDDY_NAME, pin: '', gender: 'girl' })
  const [err, setErr] = useState('')
  const ok = f.childNickname && /^\d{4}$/.test(f.pin)
  return (
    <div className="phone parent"><div className="page">
      <h1>{S.setupTitle}</h1>
      <div className="card" style={{ display: 'grid', gap: 12 }}>
        <label>{S.nickname}<input value={f.childNickname} maxLength={12} onChange={e => setF({ ...f, childNickname: e.target.value })} /></label>
        <label>{S.gender}
          <div className="seg">
            <button className={f.gender === 'girl' ? 'on' : ''} onClick={() => setF({ ...f, gender: 'girl' })}>{S.girl}</button>
            <button className={f.gender === 'boy' ? 'on' : ''} onClick={() => setF({ ...f, gender: 'boy' })}>{S.boy}</button>
          </div></label>
        <label>{S.ageBand}
          <select value={f.ageBand} onChange={e => setF({ ...f, ageBand: e.target.value })}>
            <option value="3-4">3〜4さい</option><option value="5-6">5〜6さい</option><option value="7-8">7〜8さい</option>
          </select></label>
        <label>{S.pin}<input inputMode="numeric" maxLength={4} value={f.pin} onChange={e => setF({ ...f, pin: e.target.value.replace(/\D/g, '') })} /></label>
      </div>
      {err && <div className="err">{err}</div>}
      <button className="btn" disabled={!ok} onClick={() => onDone(f).catch(e => setErr(e.message))}>{S.start}</button>
    </div></div>
  )
}

// ---------- ホーム ----------
export function Home({ s, celebrate, onBrush, onGate, onGive }: {
  s: State; celebrate: string; onBrush: () => void; onGate: () => void; onGive: (k: string) => Promise<void>
}) {
  const [mode, setMode] = useState<'grow' | 'items'>('grow')
  const [toast, setToast] = useState(celebrate)
  const [fed, setFed] = useState(false)
  const [glow, setGlow] = useState(false)
  const [idx, setIdx] = useState(0)
  const [hold, setHold] = useState(false)
  const timer = useRef<number | undefined>(undefined)
  const f = s.family
  const name = f.childNickname + suffix(f.gender)
  const keys = ITEM_ORDER.filter(k => (s.inventory[k] ?? 0) > 0)
  const cur = keys[Math.min(idx, Math.max(0, keys.length - 1))]
  const sad = s.sabori

  let msg: string
  if (toast) msg = toast
  else if (sad) msg = 'いたいよー…\nみがいて ほしいな'
  else if (s.reportedToday) msg = `${name}、\nきょうも ありがとう！\nあと${s.daysToNextItem}にち ほめてもらうと\nアイテムだよ`
  else if (s.stage <= 1) msg = '…たまごが ゆれてるよ！\nはみがきして あたためてね'
  else msg = `${name}、\nきょうの はみがき できたかな？`

  const startHold = () => { setHold(true); timer.current = window.setTimeout(() => { setHold(false); onGate() }, 2000) }
  const endHold = () => { setHold(false); window.clearTimeout(timer.current) }
  const brush = () => {
    if (s.reportedToday && s.answeredToday) { setMode('grow'); setToast(S.alreadyDone); return }
    onBrush()
  }
  const give = async () => {
    if (!cur) return
    const k = cur
    await onGive(k); setFed(true); setGlow(true); setToast(ITEM_LINES[k] ?? S.fedMsg); setMode('grow')
    window.setTimeout(() => setFed(false), 1600); window.setTimeout(() => setGlow(false), 2200)
  }

  return (
    <div className={`phone home ${s.sparkly ? 'sparkly' : ''}`}>
      <Demo s={s} />
      <div className="topbar">
        <div className="daypill"><b>{s.dayNo}</b><span>{S.dayLabel}</span></div>
        <div className="stagepill">{sad ? 'いたいよー' : s.stageName}</div>
        <div className={`gate ${hold ? 'hold' : ''}`} onPointerDown={startHold} onPointerUp={endHold} onPointerLeave={endHold} onPointerCancel={endHold}>🔒 {S.gate}{s.reportedToday && !s.approvedToday && <i className="badge" aria-label="承認待ち" />}</div>
      </div>
      <div className="sun"><SunWindow /></div>

      {mode === 'items' ? (
        <div className="itempanel">
          {cur ? (<>
            <button className="arrow" onClick={() => setIdx((idx + keys.length - 1) % keys.length)}>◀</button>
            <div>
              <div className="itemcard"><div className="pic"><ItemArt k={cur} /></div>
                <div className="nm">{ITEMS[cur].name}</div>
                {s.inventory[cur] > 1 && <span className="cnt">×{s.inventory[cur]}</span>}</div>
              <div className="dots">{keys.map((k, i) => <i key={k} className={k === cur ? 'on' : ''} data-i={i} />)}</div>
            </div>
            <button className="arrow" onClick={() => setIdx((idx + 1) % keys.length)}>▶</button>
            <div className="itemside">{ITEMS[cur].text}<div style={{ marginTop: 8 }}><button className="pillbtn" onClick={give}>{S.give}</button></div></div>
          </>) : <div className="bubble" style={{ margin: 0, flex: 1 }}>{S.noItems}</div>}
        </div>
      ) : (<>
        {sad && <div className="bubble sm demon">きょう みがけば かえるよ！</div>}
        <div className={`bubble ${sad ? 'sm' : ''}`} style={sad ? { marginTop: 26, marginRight: 130 } : undefined}>{msg}</div>
      </>)}

      <div className="floor" />
      <div className="stage">
        <div className="mat-wrap"><Mat /></div>
        <div className="duo">
          <div className={`buddy-wrap ${glow ? 'glow' : ''} ${fed ? 'bounce' : s.stage <= 1 ? 'wobble' : ''} ${sad ? 'small' : ''}`}><Buddy stage={s.stage} sad={sad} /></div>
        </div>
        {sad && <div className="demon-wrap"><Demon /></div>}
      </div>

      <nav className="nav">
        <button onClick={brush}><span className="circ"><NavIcon kind="brush" /></span>{S.tabBrush}</button>
        <button className={mode === 'grow' ? 'on' : ''} onClick={() => { setMode('grow'); setToast('') }}><span className="circ"><NavIcon kind="grow" on={mode === 'grow'} /></span>{S.tabGrow}</button>
        <button className={mode === 'items' ? 'on' : ''} onClick={() => { setMode('items'); setToast('') }}><span className="circ"><NavIcon kind="items" on={mode === 'items'} /></span>{S.tabItems}</button>
      </nav>
    </div>
  )
}

// ---------- 申告 ----------
export function Report({ onSubmit, onBack }: { onSubmit: (self: boolean) => void; onBack: () => void }) {
  return (
    <div className="phone"><div className="page">
      <button className="backbtn" onClick={onBack}>⬅ {S.back}</button>
      <div className="big-q" style={{ marginTop: 90 }}>{S.selfStarted}</div>
      <div className="choices" style={{ marginTop: 40 }}>
        <button className="pillbtn" onClick={() => onSubmit(true)}>{S.selfYes}</button>
        <button className="pillbtn" onClick={() => onSubmit(false)}>{S.selfNo}</button>
      </div>
    </div></div>
  )
}

// ---------- 3つのしつもん ----------
export function Questions({ onDone, onBack }: { onDone: (a: { axis: string; choice: number }[]) => void; onBack: () => void }) {
  const [qs, setQs] = useState<Question[] | null>(null)
  const [i, setI] = useState(0)
  const [ans, setAns] = useState<{ axis: string; choice: number }[]>([])
  const [sel, setSel] = useState<number | null>(null)
  useEffect(() => { api.questions().then(r => setQs(r.questions)) }, [])
  if (!qs) return <div className="phone"><div className="page">…</div></div>
  const q = qs[i]
  const next = () => {
    if (sel === null) return
    const a = [...ans, { axis: q.axis, choice: sel }]
    if (i + 1 < qs.length) { setAns(a); setI(i + 1); setSel(null) } else onDone(a)
  }
  return (
    <div className="phone"><div className="page">
      <button className="backbtn" onClick={onBack}>⬅ {S.back}</button>
      <div className="progress">{qs.map((_, k) => <i key={k} className={k <= i ? 'on' : ''} />)}</div>
      <div className="big-q">{q.text}</div>
      <button className="pillbtn ghost" style={{ alignSelf: 'flex-start', padding: '8px 18px', fontSize: '1rem' }} onClick={() => speak(q.text + q.choices.join('、'))}>🔊 {S.tts}</button>
      <div className="choices">
        {q.choices.map((c, k) => <button key={k} className={`pillbtn ${sel === k ? 'sel' : ''}`} onClick={() => setSel(k)}>{c}</button>)}
      </div>
      <div style={{ marginTop: 'auto', paddingTop: 24 }}>
        <button className="pillbtn wide" disabled={sel === null} style={sel === null ? { opacity: .5 } : undefined} onClick={next}>{i + 1 < qs.length ? S.qNext : S.qFinish}</button>
      </div>
    </div></div>
  )
}

// ---------- 完了（アイテム・おとなに渡す） ----------
export function Done({ s, grew, onHome }: { s: State; grew: boolean; onHome: () => void }) {
  const f = s.family
  return (
    <div className="phone"><div className="done">
      <div className="nm">{f.childNickname}<small>{suffix(f.gender)}</small></div>
      <div className="lead">{S.doneLead}</div>
      <div className="main">{S.doneMain}</div>
      <span className="star" style={{ right: 38, top: 130 }}>★</span>
      {grew && <div className="growmsg" style={{ whiteSpace: 'pre-line' }}>✨ {s.stage === 2 ? S.hatchIntro : S.grew}</div>}
      <div className="next-msg">おうちのひとに ほめてもらって<br />あと {s.daysToNextItem} にちで アイテムだよ！</div>
      <div className="hint">{S.showParent}</div>
      <button className="pillbtn wide" onClick={onHome}>{S.itemGetBack}</button>
    </div></div>
  )
}

// ---------- 承認でアイテムをもらった時（子に見える画面） ----------
export function ItemGet({ k, onDone }: { k: string; onDone: () => void }) {
  const it = ITEMS[k]
  return (
    <div className="phone"><div className="itemget">
      <div className="ig-title">{S.itemGet}</div>
      <div className="ig-pic"><ItemArt k={k} /></div>
      <span className="tag" style={{ background: ITEM_COLOR[k] }}>{it.name}</span>
      <div className="ig-tx">{it.text}</div>
      <button className="pillbtn wide" onClick={onDone}>{S.itemGetBack}</button>
    </div></div>
  )
}

// ---------- PIN ----------
export function PinGate({ onOk, onBack }: { onOk: (pin: string) => void; onBack: () => void }) {
  const [pin, setPin] = useState('')
  const [show, setShow] = useState(false)
  const [err, setErr] = useState('')
  const [shake, setShake] = useState(false)
  const ref = useRef<HTMLInputElement>(null)
  useEffect(() => ref.current?.focus(), [])
  const change = async (v: string) => {
    const d = v.replace(/\D/g, '').slice(0, 4)
    setPin(d); setErr('')
    if (d.length === 4) {
      try { await api.verify(d); onOk(d) }
      catch (e) { setErr((e as Error).message === 'PINが違います' ? S.pinWrong : (e as Error).message); setShake(true); setPin(''); window.setTimeout(() => setShake(false), 450) }
    }
  }
  return (
    <div className="phone"><div className="pin">
      <button className="backbtn" onClick={onBack}>⬅ {S.parentBack}</button>
      <div className="lab">{S.pinLabel}</div>
      <div className={`pinbox ${shake ? 'shake' : ''}`} onClick={() => ref.current?.focus()}>
        {[0, 1, 2, 3].map(i => show && pin[i] ? <span key={i} className="txt">{pin[i]}</span> : <span key={i} className={`d ${pin[i] ? '' : 'empty'}`} />)}
        <button className="eye" onClick={e => { e.stopPropagation(); setShow(!show) }} aria-label="表示切替">{show ? '🙈' : '👁'}</button>
        <input ref={ref} type="tel" inputMode="numeric" autoComplete="off" maxLength={4} value={pin} onChange={e => change(e.target.value)} />
      </div>
      {err && <div className="err">{err}</div>}
    </div></div>
  )
}

// ---------- おとな向け ----------
export function ParentMenu({ s, go, onExit }: { s: State; go: (v: 'approval' | 'weekly' | 'settings') => void; onExit: () => void }) {
  return (
    <div className="phone parent"><div className="page">
      <h1>{S.menuTitle}</h1>
      <button className="btn" onClick={() => go('approval')}>{S.menuApproval}{s.reportedToday && !s.approvedToday && <i className="badge inline" aria-label="承認待ち" />}</button>
      <button className="btn" onClick={() => go('weekly')}>{S.menuWeekly}</button>
      <button className="btn ghost" onClick={() => go('settings')}>{S.menuSettings}</button>
      <button className="btn ghost" onClick={onExit}>{S.parentBack}</button>
    </div></div>
  )
}

export function ApprovalScreen({ pin, onBack, onApproved }: { pin: string; onBack: () => void; onApproved: (r: { state: State; itemGot: string | null }) => void }) {
  const [a, setA] = useState<Approval | null>(null)
  const [text, setText] = useState('')
  const [used, setUsed] = useState('') // 入力欄に入れた「例」。そのまま送る時だけ edited=false
  const [watched, setWatched] = useState(false)
  const [hints, setHints] = useState<string[] | null>(null)
  const [hi, setHi] = useState(0)
  const [busy, setBusy] = useState(false)
  useEffect(() => { api.approval(pin).then(setA) }, [pin])
  if (!a) return <div className="phone parent"><div className="page">…</div></div>
  if (!a.canApprove) return <div className="phone parent"><div className="page"><h1>{S.approveTitle}</h1><div className="card">{S.approveNone}</div><button className="btn ghost" onClick={onBack}>{S.parentBack}</button></div></div>
  const askHint = async () => {
    if (hints) { setHi((hi + 1) % hints.length); return }
    setBusy(true)
    try { const r = await api.phraseHint(pin); setHints(r.phrases); setHi(0) } finally { setBusy(false) }
  }
  const hint = hints?.[hi]
  return (
    <div className="phone parent"><div className="page">
      <h1>{S.approveTitle}</h1>
      <div className="card"><b>{S.praiseTitle}</b>
        <ul className="facts">{a.facts.map(f => <li key={f}>{f}</li>)}</ul>
        {a.trend && <div className="trend">{a.trend}</div>}
        <div className="small" style={{ marginTop: 8 }}>{S.praiseNote}</div>
      </div>
      <div className="card"><b>{S.approveWrite}</b>
        <textarea rows={4} maxLength={80} value={text} placeholder={S.approvePlaceholder} style={{ marginTop: 8 }} onChange={e => setText(e.target.value)} />
        <button className="btn ghost" style={{ marginTop: 10, minHeight: 44 }} disabled={busy} onClick={askHint}>{hints ? S.hintNext : S.hintBtn}</button>
        {hint && (
          <div className="hint-box">
            <div>{hint}</div>
            <button className="btn ghost" style={{ marginTop: 8, minHeight: 44 }} onClick={() => { setText(hint); setUsed(hint) }}>{S.hintUse}</button>
            <div className="small" style={{ marginTop: 6 }}>{S.hintNote}</div>
          </div>
        )}
      </div>
      <label style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}><input type="checkbox" style={{ width: 24, minHeight: 24 }} checked={watched} onChange={e => setWatched(e.target.checked)} />{S.approveWatched}</label>
      {a.alreadyApproved ? <div className="card">{S.approved}</div>
        : <button className="btn good" onClick={async () => { const r = await api.approve(pin, text.trim(), text.trim() !== '' && text.trim() !== used, watched); onApproved(r) }}>{S.approveBtn}</button>}
      <button className="btn ghost" onClick={onBack}>{S.parentBack}</button>
    </div></div>
  )
}

export function WeeklyScreen({ pin, onBack }: { pin: string; onBack: () => void }) {
  const [w, setW] = useState<Weekly | null>(null)
  useEffect(() => { api.weekly(pin).then(setW) }, [pin])
  if (!w) return <div className="phone parent"><div className="page">…</div></div>
  const diff = (b: number | null) => (b === null ? '' : `（${S.weeklyPrev} ${b}日）`)
  return (
    <div className="phone parent"><div className="page">
      <h1>{S.weeklyTitle}</h1>
      <div className="card">
        <div>{S.weeklyBrush}：{w.doneDays}日 {diff(w.prevDoneDays)}</div>
        <div>{S.weeklySelf}：{w.selfDays}日 {diff(w.prevSelfDays)}</div>
        <div>{S.weeklyLongest}：{w.longestStreak}日</div>
      </div>
      <div className="card">{w.trendAvailable && w.trendText ? <>{w.trendText}<div className="small" style={{ marginTop: 8 }}>{S.weeklyNote}</div></> : S.weeklyNone}</div>
      <button className="btn ghost" onClick={onBack}>{S.parentBack}</button>
    </div></div>
  )
}

export function SettingsScreen({ pin, onBack, onDeleted }: { pin: string; onBack: () => void; onDeleted: () => void }) {
  return (
    <div className="phone parent"><div className="page">
      <h1>{S.settingsTitle}</h1>
      <button className="btn ghost" onClick={async () => { if (confirm(S.deleteConfirm)) { await api.deleteFamily(pin); onDeleted() } }}>{S.deleteAll}</button>
      <button className="btn ghost" onClick={onBack}>{S.parentBack}</button>
    </div></div>
  )
}
