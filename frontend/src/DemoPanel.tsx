import { useState } from 'react'
import { demoClock, store } from './api'

// デモ動画の撮影用。DEMO_MODE=1 のサーバーでだけ App から描画される。折りたたみ可。
const jst = (d: Date) => d.toLocaleString('ja-JP', { timeZone: 'Asia/Tokyo', month: 'numeric', day: 'numeric', weekday: 'short', hour: '2-digit', minute: '2-digit' })
const ymdJst = (d: Date) => new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Tokyo' }).format(d) // YYYY-MM-DD
const atH = (ymd: string, h: number) => `${ymd}T${String(h).padStart(2, '0')}:00:00+09:00`
const at19 = (ymd: string) => atH(ymd, 19)
const addDays = (ymd: string, n: number) => {
  const [y, m, d] = ymd.split('-').map(Number)
  return new Date(Date.UTC(y, m - 1, d + n)).toISOString().slice(0, 10)
}
const openKey = 'demoPanelOpen'
const readOpen = () => { try { return localStorage.getItem(openKey) === '1' } catch { return false } }

export function DemoPanel({ onChange }: { onChange: () => void }) {
  const [open, setOpen] = useState(readOpen)
  const [, bump] = useState(0)
  const cur = demoClock.now ? new Date(demoClock.now) : new Date()
  const set = (iso: string | null) => { demoClock.now = iso; bump(n => n + 1); onChange() }
  // 保存している家族IDを消し、仮の日時を「今日の19:00」にして、名前入力の画面から始め直す
  const restart = () => {
    if (!window.confirm('いまのデモデータは消えます。1日目からはじめますか？')) return
    store.fid = null
    demoClock.now = at19(ymdJst(new Date()))
    location.reload()
  }
  const toggle =() => { const v = !open; setOpen(v); try { localStorage.setItem(openKey, v ? '1' : '0') } catch { /* noop */ } }
  return (
    <>
      {demoClock.now && <div className="demo-banner">デモ用モード（日付を操作中）</div>}
      <div className={`demo-panel ${open ? 'open' : ''}`}>
        <button className="demo-toggle" onClick={toggle} aria-label="日付操作パネル">{open ? '×' : '📅'}</button>
        {open && (
          <div className="demo-body">
            <div className="demo-now">いまの日時（仮）<b>{jst(cur)}</b></div>
            <div className="demo-row">
              <button onClick={() => set(at19(addDays(ymdJst(cur), -1)))}>-1日</button>
              <button onClick={() => set(at19(addDays(ymdJst(cur), 1)))}>+1日</button>
            </div>
            <div className="demo-row">
              <button onClick={() => set(atH(ymdJst(cur), 7))}>朝（7:00）</button>
              <button onClick={() => set(atH(ymdJst(cur), 13))}>昼（13:00）</button>
              <button onClick={() => set(atH(ymdJst(cur), 19))}>夜（19:00）</button>
            </div>
            <div className="demo-row">
              <input type="date" value={ymdJst(cur)} onChange={e => e.target.value && set(at19(e.target.value))} />
            </div>
            <div className="demo-row"><button onClick={() => set(null)}>本当の現在時刻にもどす</button></div>
            <div className="demo-row"><button onClick={restart}>1日目からはじめる（新しい家族）</button></div>
          </div>
        )}
      </div>
    </>
  )
}
