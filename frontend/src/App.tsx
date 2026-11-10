import { useCallback, useState } from 'react'
import { api, store, demoClock, type State } from './api'
import * as V from './screens'
import { DemoPanel } from './DemoPanel'

type View = 'itemget' | 'start' | 'setup' | 'home' | 'report' | 'questions' | 'done' | 'pin' | 'menu' | 'approval' | 'weekly' | 'settings'

export default function App() {
  const [view, setView] = useState<View>('start')
  const [s, setS] = useState<State | null>(null)
  const [pin, setPin] = useState('')
  const [grew, setGrew] = useState(false)
  const [celebrate, setCelebrate] = useState('')
  const [got, setGot] = useState('')
  const [prevStage, setPrevStage] = useState(1)

  const refresh = useCallback(async () => {
    try { setS(await api.state()); setView('home') } catch { store.fid = null; setView('setup') }
  }, [])
  const tapStart = () => (store.fid ? refresh() : setView('setup'))
  const home = async (msg = '') => { setCelebrate(msg); await refresh(); setPin('') }

  if (view === 'start') return <V.Start onTap={tapStart} />
  if (view === 'setup') return <V.Setup onDone={async b => { store.fid = (await api.createFamily(b)).familyId; await refresh() }} />
  if (!s) return null

  // デモモードのサーバーだけ、日付操作パネルを出す。日付を動かしたら state を取り直して反映する
  demoClock.enabled = !!s.demoMode // 本番では false のまま → 窓の外も本物の時刻
  return <>{s.demoMode &&<DemoPanel onChange={refresh} />}{screen(s)}</>

  function screen(s: State) {
  switch (view) {
    case 'home':
      return <V.Home key={s.today + s.totalDays + celebrate} s={s} celebrate={celebrate}
        onGate={() => setView('pin')}
        onGive={async k => setS(await api.giveItem(k))}
        onBrush={() => setView(s.reportedToday ? 'questions' : 'report')} />
    case 'report':
      return <V.Report onBack={() => home()} onSubmit={async self => { setPrevStage(s.stage); setS(await api.report(self)); setView('questions') }} />
    case 'questions':
      return <V.Questions onBack={() => home()} onDone={async a => {
        const r = await api.answers(a); setS(r.state); setGrew(r.state.stage > prevStage); setView('done')
      }} />
    case 'done':
      return <V.Done s={s} grew={grew} onHome={() => home()} />
    case 'pin':
      return <V.PinGate onBack={() => home()} onOk={p => { setPin(p); setView('menu') }} />
    case 'menu':
      return <V.ParentMenu s={s} go={setView} onExit={() => home()} />
    case 'approval':
      return <V.ApprovalScreen pin={pin} onBack={() => setView('menu')}
        onApproved={r => (r.itemGot ? (setGot(r.itemGot), setView('itemget')) : home('ほめてもらえて うれしい！'))} />
    case 'itemget':
      return <V.ItemGet k={got} onDone={() => home('ほめてもらえて うれしい！')} />
    case 'weekly':
      return <V.WeeklyScreen pin={pin} onBack={() => setView('menu')} />
    case 'settings':
      return <V.SettingsScreen pin={pin} onBack={() => setView('menu')} onDeleted={() => { store.fid = null; setPin(''); setView('setup') }} />
  }
  }
}
