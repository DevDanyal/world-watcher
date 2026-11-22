import { useEffect, useState } from 'react'

const API_BASE = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')

async function api(path, opts = {}) {
  const url = path.startsWith('http') ? path : `${API_BASE}${path}`
  let res
  try {
    res = await fetch(url, { credentials: 'include', headers: { 'Content-Type': 'application/json' }, ...opts })
  } catch {
    throw new Error(API_BASE ? `Cannot reach backend at ${API_BASE}.` : 'Backend not configured. Set VITE_API_URL in Vercel.')
  }
  if (!res.ok) {
    let detail
    try { detail = (await res.json()).detail } catch {}
    if (!API_BASE && (res.status === 404 || res.status === 405)) throw new Error('Backend not configured. Set VITE_API_URL in Vercel.')
    throw new Error(detail || `Request failed (${res.status})`)
  }
  return res.json()
}

export default function AlertsView({ onToast }) {
  const [rules, setRules] = useState([])
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [name, setName] = useState('Keyword alert')
  const [keyword, setKeyword] = useState('X')
  const [importance, setImportance] = useState(7)

  const load = async () => {
    setLoading(true); setError('')
    try {
      const [r, h] = await Promise.all([api('/api/alerts/rules'), api('/api/alerts/history?limit=50')])
      setRules(r); setHistory(h)
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const createRule = async (e) => {
    e.preventDefault()
    try {
      await api('/api/alerts/rules', { method: 'POST', body: JSON.stringify({
        name, source_type: 'news_rss', enabled: true, cooldown_seconds: 300,
        channels: { dashboard: true, desktop: false, telegram: false },
        conditions: [{ type: 'keyword', value: keyword }, { type: 'importance_gte', value: Number(importance) }],
      }) })
      onToast?.('Rule created', 'success')
      setName('Keyword alert')
      await load()
    } catch (e) { onToast?.(e.message, 'error') }
  }

  const del = async (id) => {
    try { await api(`/api/alerts/rules/${id}`, { method: 'DELETE' }); onToast?.('Rule deleted', 'success'); load() }
    catch (e) { onToast?.(e.message, 'error') }
  }

  return (
    <div className="page-grid">
      <section className="panel">
        <div className="panel-head"><h2>ALERT RULES</h2><span>{rules.length}</span></div>
        <div className="page-body">
          <form className="inline-form" onSubmit={createRule}>
            <input className="auth-input" value={name} onChange={e => setName(e.target.value)} placeholder="Rule name" required />
            <input className="auth-input" value={keyword} onChange={e => setKeyword(e.target.value)} placeholder="Keyword" required />
            <input className="auth-input" type="number" min="1" max="10" value={importance} onChange={e => setImportance(e.target.value)} />
            <button className="auth-btn" type="submit">Add Rule</button>
          </form>
          {loading && <div className="muted">Loading rules...</div>}
          {error && <div className="auth-error">{error}</div>}
          {!loading && !rules.length && <div className="muted">No rules yet.</div>}
          {rules.map(r => (
            <div key={r.id} className="list-row">
              <div>
                <div>{r.name}</div>
                <div className="muted small">{r.source_type} · cooldown {r.cooldown_seconds}s · {JSON.stringify(r.conditions_json || r.conditions)}</div>
              </div>
              <button className="auth-btn small danger" onClick={() => del(r.id)}>Delete</button>
            </div>
          ))}
        </div>
      </section>
      <section className="panel">
        <div className="panel-head"><h2>ALERT HISTORY</h2><span>{history.length}</span></div>
        <div className="page-body scroll-body">
          {loading && <div className="muted">Loading history...</div>}
          {!loading && !history.length && <div className="muted">No alert history.</div>}
          {history.map(h => (
            <div key={h.id} className="list-row">
              <div>
                <div>{h.title} <span className="muted">imp {h.importance}</span></div>
                <div className="muted small">{h.reason}</div>
                <div className="muted small">{String(h.triggered_at || '').replace('T',' ').slice(0,19)}</div>
              </div>
              <span className="badge">{h.source_type}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
