// 相棒の見た目は「キー」で引く。Figmaの最終デザインが来たら、ここだけ画像に差し替える。
// キー形式: buddy_stage{1-4}_{idle|happy}
const EMOJI: Record<number, string> = { 1: '🥚', 2: '🐣', 3: '🐥', 4: '🦖' }

export function Buddy({ stage, mood = 'idle', cls = '' }: { stage: number; mood?: 'idle' | 'happy'; cls?: string }) {
  const key = `buddy_stage${stage}_${mood}`
  return <div className={`buddy ${cls}`} data-asset={key} role="img" aria-label={key}>{EMOJI[stage] ?? '🥚'}</div>
}
