export default function WorkerCard({ worker }) {
  return (
    <article className={`worker-card status-${worker.status}`}>
      <div className="worker-head">
        <div>
          <div className="worker-name">{worker.name}</div>
          <div className="worker-type">{worker.task_type || 'unassigned'}</div>
        </div>
        <span className={`badge ${worker.status}`}>{worker.status}</span>
      </div>
      <div className="worker-action">{worker.current_action}</div>
      <div className="progress-track">
        <div className="progress-fill" style={{ width: `${worker.progress || 0}%` }} />
      </div>
      <div className="worker-foot">
        <span>ID {worker.id}</span>
        <span>{worker.progress || 0}%</span>
      </div>
    </article>
  )
}
