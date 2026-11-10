// 画像は「名前」で引く。frontend/public/art/<name>.png を置くと、自動で仮のSVGから差し替わる。
//   buddy_egg / buddy_baby / buddy_minarai / buddy_adult / buddy_sad / buddy_start / demon
//   item_calcium / item_phosphorus / item_vitd / item_vitc
//   sun_window_day / sun_window_morning / sun_window_night / mat / nav_{brush,grow,items}_{on,off}
import { useState, type ReactNode } from 'react'
import { demoClock } from './api'

export function Art({ name, cls = '', children }: { name: string; cls?: string; children: ReactNode }) {
  // 仮のSVGを先に出し、画像が実在して読み込めた時だけ差し替える（空白・壊れ画像を出さない）
  const [ok, setOk] = useState(false)
  const src = `/art/${name}.png`
  if (ok) return <img className={cls} src={src} alt="" data-art={name} draggable={false} />
  return <>{children}<img src={src} alt="" style={{ display: 'none' }} onLoad={() => setOk(true)} /></>
}

const NAVY = '#0B2A7A'
const TOOTH = 'M24,70 C24,22 76,14 100,40 C124,14 176,22 176,70 C176,108 156,118 156,152 L148,200 C146,212 128,212 126,200 L118,160 C112,150 88,150 82,160 L74,200 C72,212 54,212 52,200 L44,152 C44,118 24,108 24,70 Z'

function Eyes({ y = 88, r = 14 }: { y?: number; r?: number }) {
  return <g>{[78, 122].map(x => (
    <g key={x}><ellipse cx={x} cy={y} rx={9} ry={r} fill={NAVY} /><circle cx={x - 2} cy={y - r / 2} r={3.2} fill="#fff" /></g>))}</g>
}

export function ToothSvg({ kind }: { kind: 'baby' | 'minarai' | 'adult' | 'sad' | 'start' }) {
  const fill = kind === 'sad' ? '#FFF0A0' : '#fff'
  return (
    <svg viewBox="0 0 200 220" className="art-svg" aria-hidden>
      <ellipse cx="100" cy="212" rx="64" ry="9" fill="rgba(0,30,110,.25)" />
      {kind === 'adult' && <g stroke="#fff" strokeWidth="22" strokeLinecap="round" fill="none">
        <path d="M34,112 C6,108 8,76 22,60" /><path d="M166,112 C194,108 192,76 178,60" /></g>}
      {(kind === 'minarai' || kind === 'start' || kind === 'baby') && <g fill="#fff">
        <ellipse cx="22" cy="118" rx="16" ry="11" transform="rotate(-25 22 118)" /><ellipse cx="178" cy="118" rx="16" ry="11" transform="rotate(25 178 118)" /></g>}
      <path d={TOOTH} fill={fill} />
      <path d="M52,52 C80,40 120,40 148,52" stroke={NAVY} strokeWidth="2.5" fill="none" opacity=".7" />
      <Eyes y={kind === 'baby' ? 92 : 88} r={kind === 'baby' ? 16 : 14} />
      {kind === 'baby' && <><circle cx="58" cy="108" r="7" fill="#FFB1B1" opacity=".8" /><circle cx="142" cy="108" r="7" fill="#FFB1B1" opacity=".8" />
        <circle cx="100" cy="118" r="9" fill="#FF5A5A" stroke="#4A7BFF" strokeWidth="3" /></>}
      {(kind === 'minarai' || kind === 'start') && <ellipse cx="100" cy="118" rx="6" ry="9" fill="#E0553A" />}
      {kind === 'adult' && <><path d="M62,70 L90,76 M138,70 L110,76" stroke={NAVY} strokeWidth="3" /><path d="M88,120 Q100,128 112,120" stroke={NAVY} strokeWidth="3" fill="none" /></>}
      {kind === 'sad' && <><path d="M64,70 L92,78 M136,70 L108,78" stroke={NAVY} strokeWidth="3" /><path d="M88,126 Q100,116 112,126" stroke={NAVY} strokeWidth="3" fill="none" />
        <path d="M70,108 q-4,10 0,14 q4,-4 0,-14z M130,108 q-4,10 0,14 q4,-4 0,-14z" fill="#38BDF8" /></>}
    </svg>
  )
}

export function EggSvg() {
  return (
    <svg viewBox="0 0 200 220" className="art-svg" aria-hidden>
      <ellipse cx="100" cy="212" rx="58" ry="8" fill="rgba(0,30,110,.25)" />
      <path d="M100,10 C150,10 175,80 175,130 C175,180 140,210 100,210 C60,210 25,180 25,130 C25,80 50,10 100,10Z" fill="#fff" />
      {[[70, 60, 9], [130, 90, 11], [60, 140, 8], [120, 165, 10], [92, 110, 6]].map(([x, y, r], i) => <circle key={i} cx={x} cy={y} r={r} fill="#8CBCFF" />)}
      <path d="M40,120 L62,104 L82,122 L102,102 L124,124 L146,104 L162,120" stroke={NAVY} strokeWidth="3" fill="none" strokeLinejoin="round" />
    </svg>
  )
}

export function DemonSvg() {
  return (
    <svg viewBox="0 0 160 170" className="art-svg" aria-hidden>
      <ellipse cx="80" cy="162" rx="56" ry="7" fill="rgba(0,30,110,.25)" />
      <path d="M22,150 C6,70 28,24 80,24 C132,24 154,70 138,150 Z" fill="#5A0F63" />
      <path d="M42,36 L30,8 L58,28 Z M118,36 L130,8 L102,28 Z" fill="#5A0F63" />
      <path d="M140,140 q22,-6 14,16 q-8,-6 -14,-2z" fill="#5A0F63" />
      {[58, 102].map(x => <g key={x}><ellipse cx={x} cy="78" rx="14" ry="17" fill="#B7B315" /><ellipse cx={x} cy="80" rx="6" ry="11" fill="#fff" /></g>)}
      <path d="M62,112 Q80,124 98,112" stroke="#FF5FA8" strokeWidth="6" fill="none" strokeLinecap="round" />
    </svg>
  )
}

export function ItemSvg({ k }: { k: string }) {
  const bg = { calcium: '#2FD3B6', phosphorus: '#E8A010', vitd: '#7ED321', vitc: '#FF4B4B' }[k] ?? '#999'
  return (
    <svg viewBox="0 0 100 100" className="art-svg" aria-hidden>
      <rect width="100" height="100" rx="10" fill={bg} />
      {k === 'calcium' && <><ellipse cx="38" cy="46" rx="24" ry="14" fill="#0E4C92" /><path d="M58,46 L74,34 L74,58 Z" fill="#0E4C92" />
        <rect x="52" y="52" width="32" height="36" fill="#0E4C92" /><path d="M52,52 L60,40 L84,40 L84,52 Z" fill="#CDEFF0" /></>}
      {k === 'phosphorus' && <><ellipse cx="38" cy="40" rx="24" ry="20" fill="#FFF3A6" /><circle cx="40" cy="42" r="9" fill="#F08A24" />
        <ellipse cx="62" cy="68" rx="22" ry="18" fill="#FFF3A6" /><circle cx="63" cy="68" r="8" fill="#F08A24" /></>}
      {k === 'vitd' && <><path d="M18,52 Q50,6 82,52 Z" fill="#5A3A1E" /><rect x="42" y="50" width="16" height="30" rx="6" fill="#D9C7A0" />
        <path d="M70,60 l14,10 -6,14 -14,-6z" fill="#0F6B3A" /></>}
      {k === 'vitc' && <><path d="M26,40 Q50,30 74,40 Q70,80 50,90 Q30,80 26,40Z" fill="#FF8FA3" />
        {[[40, 54], [52, 62], [60, 48], [46, 74]].map(([x, y], i) => <circle key={i} cx={x} cy={y} r="2.5" fill="#7A1230" />)}
        <path d="M38,38 L50,26 L62,38Z" fill="#2E8B3A" /></>}
    </svg>
  )
}

// 時間帯で窓を切り替える（4:00〜10:00 朝 / 10:00〜17:00 昼 / それ以外 夜）。日付の区切りと同じ日本時間で判定
function windowKind(now: Date = new Date()): 'morning' | 'day' | 'night' {
  const h = (now.getUTCHours() + 9) % 24
  return h >= 4 && h < 10 ? 'morning' : h >= 10 && h < 17 ? 'day' : 'night'
}

export function SunWindow() {
  return (
    <Art name={`sun_window_${windowKind(demoClock.effectiveNow())}`} cls="sun-img">
      <svg viewBox="0 0 150 150" className="art-svg" aria-hidden>
        <circle cx="75" cy="75" r="70" fill="#F5E6C8" /><circle cx="75" cy="75" r="60" fill="#1E8CFF" />
        <circle cx="108" cy="42" r="14" fill="#FFD928" />
        <ellipse cx="38" cy="50" rx="18" ry="8" fill="#fff" /><ellipse cx="108" cy="112" rx="16" ry="7" fill="#fff" />
        <path d="M75,15 V135 M15,75 H135" stroke="#F5E6C8" strokeWidth="9" />
      </svg>
    </Art>
  )
}

export function Mat() {
  return (
    <Art name="mat" cls="mat-img">
      <svg viewBox="0 0 200 220" className="art-svg" aria-hidden><path d={TOOTH} fill="#3F86D6" /></svg>
    </Art>
  )
}

export function Buddy({ stage, sad = false, cls = '' }: { stage: number; sad?: boolean; cls?: string }) {
  if (sad) return <Art name="buddy_sad" cls={cls}><ToothSvg kind="sad" /></Art>
  if (stage <= 1) return <Art name="buddy_egg" cls={cls}><EggSvg /></Art>
  if (stage === 2) return <Art name="buddy_baby" cls={cls}><ToothSvg kind="baby" /></Art>
  if (stage === 3) return <Art name="buddy_minarai" cls={cls}><ToothSvg kind="minarai" /></Art>
  return <Art name="buddy_adult" cls={cls}><ToothSvg kind="adult" /></Art>
}
export const Demon = () => <Art name="demon"><DemonSvg /></Art>
export const StartBuddy = () => <Art name="buddy_start"><ToothSvg kind="start" /></Art>
export const ItemArt = ({ k }: { k: string }) => <Art name={`item_${k}`}><ItemSvg k={k} /></Art>

export function NavIcon({ kind, on = false }: { kind: 'brush' | 'grow' | 'items'; on?: boolean }) {
  return (
    <Art name={`nav_${kind}_${on ? 'on' : 'off'}`}>
      <svg viewBox="0 0 64 64" className="art-svg" aria-hidden>
        {kind === 'brush' && <g transform="rotate(-40 32 32)"><rect x="26" y="26" width="12" height="34" rx="6" fill={NAVY} /><rect x="22" y="6" width="20" height="22" rx="4" fill={NAVY} />
          {[26, 31, 36].map(x => <rect key={x} x={x} y="2" width="3" height="10" fill="#fff" />)}</g>}
        {kind === 'grow' && <path d="M8,26 C8,10 26,6 32,14 C38,6 56,10 56,26 C56,40 48,42 48,54 C48,60 42,60 41,54 L38,46 C35,43 29,43 26,46 L23,54 C22,60 16,60 16,54 C16,42 8,40 8,26Z" fill="currentColor" />}
        {kind === 'items' && <g fill={NAVY}><rect x="10" y="26" width="44" height="30" rx="5" /><rect x="6" y="18" width="52" height="12" rx="4" />
          <rect x="28" y="18" width="8" height="38" fill="#fff" /><path d="M32,18 C20,4 12,16 28,18 M32,18 C44,4 52,16 36,18" stroke={NAVY} strokeWidth="4" fill="none" /></g>}
      </svg>
    </Art>
  )
}
