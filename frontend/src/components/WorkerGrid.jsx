import WorkerCard from './WorkerCard'

export default function WorkerGrid({ workers }) {
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>WORKER GRID</h2>
        <span>{workers.length} workers</span>
      </div>
      <div className="worker-grid">
        {workers.map((w) => <WorkerCard key={w.id} worker={w} />)}
      </div>
    </section>
  )
}
