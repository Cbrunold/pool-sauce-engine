import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

// Crash catcher — persist the last error so it survives a page reload (e.g. a
// mobile tab purge), and surface it on the welcome screen for diagnosis.
function recordError(label: string, detail: unknown) {
  try {
    const msg =
      detail instanceof Error
        ? `${detail.name}: ${detail.message}`
        : String(detail)
    localStorage.setItem(
      'pse_last_error',
      JSON.stringify({ label, msg, at: new Date().toISOString() })
    )
  } catch { /* ignore */ }
}
window.addEventListener('error', (e) => recordError('error', e.error ?? e.message))
window.addEventListener('unhandledrejection', (e) => recordError('promise', e.reason))

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
