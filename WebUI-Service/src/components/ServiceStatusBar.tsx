const SERVICES = [
  { label: "n8n Pipeline", status: "Active" },
  { label: "Local LLM", status: "Online" },
  { label: "RAG Index", status: "Connected" },
] as const;

export function ServiceStatusBar() {
  return (
    <div className="sidebar-status-bar">
      <p className="sidebar-status-title">System status</p>
      <ul className="sidebar-status-list">
        {SERVICES.map((svc) => (
          <li key={svc.label} className="sidebar-status-item">
            <span className="sidebar-status-dot" aria-hidden="true" />
            <span className="sidebar-status-label">
              {svc.label}: <span className="sidebar-status-value">{svc.status}</span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
