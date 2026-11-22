export default function StatsBar({ stats }) {
  const items = [
    { label: 'RUNNING', value: stats.running ?? 0, cls: 'running' },
    { label: 'DONE', value: stats.done ?? 0, cls: 'done' },
    { label: 'ERRORS', value: stats.errors ?? 0, cls: 'error' },
    { label: 'QUEUED', value: stats.queued ?? 0, cls: 'queued' },
  ]
  return (
    <section className="stats-bar">
      {items.map((i) => (
        <div key={i.label} className={`stat ${i.cls}`}>
          <div className="stat-label">{i.label}</div>
          <div className="stat-value">{i.value}</div>
        </div>
      ))}
    </section>
  )
}
