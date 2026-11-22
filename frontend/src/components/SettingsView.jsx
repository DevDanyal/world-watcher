import { useEffect, useState } from 'react'

export default function SettingsView() {
  const [settings, setSettings] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    const API_BASE = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')
    fetch(`${API_BASE}/api/settings`, { credentials: 'include' })
      .then(r => r.ok ? r.json() : Promise.reject(new Error('failed to load settings')))
      .then(setSettings).catch(e => setError(e.message))
  }, [])
  return (
    <section className="panel">
      <div className="panel-head"><h2>SETTINGS</h2><span>read-only snapshot</span></div>
      <div className="page-body">
        {error && <div className="auth-error">{error}</div>}
        {!settings && !error && <div className="muted">Loading settings...</div>}
        {settings && <div className="settings-grid">
          {Object.entries(settings).map(([k, v]) => (
            <div key={k} className="setting-row"><span className="muted">{k}</span><span>{typeof v === 'object' ? JSON.stringify(v) : String(v)}</span></div>
          ))}
        </div>}
        <div className="muted small">Sensitive keys are masked by configuration flags. Edit `.env` for secret values and restart backend.</div>
      </div>
    </section>
  )
}
