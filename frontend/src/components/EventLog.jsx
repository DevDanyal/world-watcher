import { useEffect, useRef } from 'react'

export default function EventLog({ events }) {
  const ref = useRef(null)
  useEffect(() => {
    const el = ref.current
    if (el) el.scrollTop = el.scrollHeight
  }, [events])

  return (
    <section className="panel event-panel">
      <div className="panel-head">
        <h2>LIVE EVENT LOG</h2>
        <span>{events.length} events</span>
      </div>
      <div className="event-log" ref={ref}>
        {events.slice(-200).map((e, i) => (
          <div key={`${e.ts}-${i}`} className={`event-row level-${e.level || 'info'}`}>
            <span className="event-ts">{(e.ts || '').replace('T', ' ').slice(11, 19)}</span>
            <span className="event-level">{(e.level || 'info').toUpperCase()}</span>
            <span className="event-msg">{e.message}</span>
          </div>
        ))}
      </div>
    </section>
  )
}
