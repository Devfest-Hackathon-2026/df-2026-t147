import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource/dela-gothic-one/japanese-400.css'
import '@fontsource/dela-gothic-one/latin-400.css'
import '@fontsource/m-plus-rounded-1c/japanese-700.css'
import '@fontsource/m-plus-rounded-1c/latin-700.css'
import '@fontsource/m-plus-rounded-1c/japanese-400.css'
import '@fontsource/m-plus-rounded-1c/latin-400.css'
import './theme.css'
import App from './App'

// デザインは 402×874 基準。縦が足りない端末では全体を縮小して、重なりを防ぐ
function fit() {
  const w = window.innerWidth
  const h = window.visualViewport?.height ?? window.innerHeight
  const k = Math.max(0.5, Math.min(1, w / 402, h / 874))
  document.documentElement.style.setProperty('--k', String(k))
}
fit()
window.addEventListener('resize', fit)
window.addEventListener('orientationchange', fit)
window.visualViewport?.addEventListener('resize', fit)

createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>)
