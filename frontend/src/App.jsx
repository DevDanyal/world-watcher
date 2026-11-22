import { useEffect, useMemo, useState } from 'react'
import StatsBar from './components/StatsBar'
import WorkerGrid from './components/WorkerGrid'
import EventLog from './components/EventLog'
import VoicePanel from './components/VoicePanel'
import AlertsView from './components/AlertsView'
import SettingsView from './components/SettingsView'
import ToastStack from './components/ToastStack'

const API_BASE = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')
const WS_BASE = (import.meta.env.VITE_WS_URL || '').replace(/\/$/, '')

function wsUrl() {
  if (WS_BASE) return `${WS_BASE}/ws/workers`
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  return `${proto}://${location.host}/ws/workers`
}

function formatApiError(detail, status, url) {
  if (Array.isArray(detail)) {
    return detail.map((d) => d.msg || JSON.stringify(d)).join('; ')
  }
  if (detail && typeof detail === 'object') return detail.msg || JSON.stringify(detail)
  if (typeof detail === 'string' && detail) return detail
  if (!API_BASE && (status === 404 || status === 405)) {
    return 'Backend is not configured for this frontend. Set VITE_API_URL and VITE_WS_URL in Vercel to your deployed backend URL.'
  }
  if (status === 404 || status === 405) {
    return `API endpoint not found (${status}) at ${url}. Check VITE_API_URL points to the backend.`
  }
  return `Request failed (${status})`
}

async function api(path, opts = {}) {
  const url = path.startsWith('http') ? path : `${API_BASE}${path}`
  let res
  try {
    res = await fetch(url, {
      credentials: 'include',
      headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
      ...opts,
    })
  } catch (err) {
    const hint = API_BASE
      ? `Cannot reach backend at ${API_BASE}. Check that the backend is running and allows this origin in CORS_ORIGINS.`
      : 'Backend is not configured. Set VITE_API_URL and VITE_WS_URL in Vercel to your deployed backend URL.'
    throw new Error(hint)
  }
  if (!res.ok) {
    let detail
    const contentType = res.headers.get('content-type') || ''
    if (contentType.includes('application/json')) {
      try { detail = (await res.json()).detail } catch {}
    }
    throw new Error(formatApiError(detail, res.status, url))
  }
  return res.json()
}

export default function App() {
  const [auth, setAuth] = useState({ loading: true, initialized: false, authenticated: false })
  const [password, setPassword] = useState('')
  const [authError, setAuthError] = useState('')
  const [workers, setWorkers] = useState([])
  const [stats, setStats] = useState({ running: 0, done: 0, errors: 0, queued: 0 })
  const [events, setEvents] = useState([])
  const [connected, setConnected] = useState(false)
  const [reconnecting, setReconnecting] = useState(false)
  const [view, setView] = useState('dashboard')
  const [toasts, setToasts] = useState([])
  const [loadingSnapshot, setLoadingSnapshot] = useState(true)

  const pushToast = (message, type = 'info') => {
    const id = Date.now() + Math.random()
    setToasts((t) => [...t, { id, message, type }])
    setTimeout(() => setToasts((t) => t.filter(x => x.id !== id)), 3500)
  }

  useEffect(() => {
    api('/api/auth/status')
      .then((s) => setAuth({ loading: false, ...s }))
      .catch(() => setAuth({ loading: false, initialized: false, authenticated: false }))
  }, [])

  useEffect(() => {
    if (!auth.authenticated) return
    let ws
    let timer
    let closed = false
    let seenOpen = false
    setLoadingSnapshot(true)
    const connect = () => {
      setReconnecting(seenOpen)
      ws = new WebSocket(wsUrl())
      ws.onopen = () => { setConnected(true); setReconnecting(false); seenOpen = true }
      ws.onclose = () => {
        setConnected(false)
        if (!closed) { setReconnecting(true); timer = setTimeout(connect, 1500) }
      }
      ws.onerror = () => setConnected(false)
      ws.onmessage = (ev) => {
        const msg = JSON.parse(ev.data)
        if (msg.type === 'snapshot') {
          setWorkers(msg.workers || [])
          setStats(msg.stats || { running: 0, done: 0, errors: 0, queued: 0 })
          setEvents(msg.events || [])
          setLoadingSnapshot(false)
        } else if (msg.type === 'worker_update') {
          setWorkers((prev) => {
            const next = [...prev]
            const idx = next.findIndex((w) => w.id === msg.worker.id)
            if (idx >= 0) next[idx] = msg.worker
            else next.push(msg.worker)
            return next.sort((a, b) => a.id - b.id)
          })
        } else if (msg.type === 'stats') {
          setStats(msg.stats)
        } else if (msg.type === 'event' || msg.type === 'alert') {
          const event = msg.event || {
            ts: msg.alert?.triggered_at,
            level: 'alert',
            message: `ALERT: ${msg.alert?.rule_name} - ${msg.alert?.title}`,
          }
          setEvents((prev) => [...prev.slice(-299), event])
          if (msg.type === 'alert') pushToast(`Alert: ${msg.alert?.rule_name || msg.alert?.title || 'triggered'}`, 'alert')
        }
      }
    }
    connect()
    return () => { closed = true; clearTimeout(timer); ws?.close() }
  }, [auth.authenticated])

  const title = useMemo(() => `WORLD WATCHER ${connected ? '● LIVE' : reconnecting ? '◌ RECONNECTING' : '○ OFFLINE'}`, [connected, reconnecting])

  const submitAuth = async (e) => {
    e.preventDefault()
    setAuthError('')
    try {
      const path = auth.initialized ? '/api/auth/login' : '/api/auth/setup'
      await api(path, { method: 'POST', body: JSON.stringify({ password }) })
      setPassword('')
      setAuth({ loading: false, initialized: true, authenticated: true })
    } catch (err) {
      setAuthError(err.message)
    }
  }

  const logout = async () => {
    await api('/api/auth/logout', { method: 'POST' }).catch(() => {})
    setConnected(false)
    setWorkers([])
    setEvents([])
    setAuth((a) => ({ ...a, authenticated: false, initialized: true }))
  }

  if (auth.loading) return <div className="auth-wrap"><div className="auth-card">Loading...</div></div>
  if (!auth.authenticated) {
    return (
      <div className="auth-wrap">
        <form className="auth-card" onSubmit={submitAuth}>
          <div className="eyebrow">WORLD WATCHER</div>
          <h1>{auth.initialized ? 'Login' : 'Set Initial Password'}</h1>
          <p className="auth-copy">{auth.initialized ? 'Enter your password to access the dashboard.' : 'Create a password for first-run setup.'}</p>
          <input className="auth-input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Password (min 8 chars)" minLength={8} required />
          {authError && <div className="auth-error">{authError}</div>}
          <button className="auth-btn" type="submit">{auth.initialized ? 'Login' : 'Create Password'}</button>
        </form>
      </div>
    )
  }

  return (
    <div className="app">
      <header className="topbar">
        <div>
          <div className="eyebrow">REAL-TIME MONITORING CONSOLE</div>
          <h1>{title}</h1>
        </div>
        <div className="topbar-meta">
          <span className={`ws-pill ${connected ? 'ok' : 'warn'}`}>WS: {connected ? 'connected' : 'reconnecting'}</span>
          <span>workers: {workers.length}</span>
          <button className="auth-btn small" onClick={logout}>Logout</button>
        </div>
      </header>
      <nav className="nav-bar">
        {['dashboard','alerts','settings'].map(v => <button key={v} className={`nav-btn ${view===v?'active':''}`} onClick={() => setView(v)}>{v.toUpperCase()}</button>)}
      </nav>
      {reconnecting && <div className="banner warn">WebSocket reconnecting… live data may be stale.</div>}
      {view === 'dashboard' && <>
        <StatsBar stats={stats} />
        <main className="main-grid with-voice">
          {loadingSnapshot ? <div className="panel loading-panel">Loading live workers…</div> : <WorkerGrid workers={workers} />}
          <VoicePanel />
        </main>
        <EventLog events={events} />
      </>}
      {view === 'alerts' && <AlertsView onToast={pushToast} />}
      {view === 'settings' && <SettingsView />}
      <ToastStack toasts={toasts} />
    </div>
  )
}
