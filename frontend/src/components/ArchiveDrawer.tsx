import type { SnapshotRead, WeeklyReport } from "../lib/apiClient";

interface ArchiveDrawerProps {
  open: boolean;
  snapshots: SnapshotRead[];
  reports: WeeklyReport[];
  latestReport: WeeklyReport | null;
  busy: boolean;
  onClose: () => void;
  onCaptureSnapshot: () => void;
  onGenerateReport: () => void;
}

function reportSummary(report: WeeklyReport): string {
  const raw = report.content.summary;
  return typeof raw === "string" && raw.length > 0 ? raw : "Weekly report ready.";
}

export function ArchiveDrawer({
  open,
  snapshots,
  reports,
  latestReport,
  busy,
  onClose,
  onCaptureSnapshot,
  onGenerateReport,
}: ArchiveDrawerProps) {
  return (
    <>
      <div className={`drawer-backdrop ${open ? "visible" : ""}`} onClick={onClose} />
      <aside className={`drawer drawer-wide ${open ? "open" : ""}`}>
        <div className="drawer-header">
          <div className="drawer-title">archive</div>
          <button className="drawer-close" onClick={onClose}>
            x
          </button>
        </div>

        <div className="drawer-section">
          <div className="drawer-label">snapshot studio</div>
          <div className="drawer-actions-row">
            <button className="drawer-action" onClick={onCaptureSnapshot} disabled={busy}>
              {busy ? "capturing..." : "capture state"}
            </button>
          </div>
          {snapshots.length === 0 ? (
            <div className="drawer-empty">capture your first graph-to-art snapshot.</div>
          ) : (
            <div className="snapshot-grid">
              {snapshots.slice(0, 6).map((snapshot) => (
                <article key={snapshot.id} className="snapshot-tile">
                  <img
                    src={snapshot.thumbnail_url ?? snapshot.image_url}
                    alt={snapshot.caption || "ThoughtGraph snapshot"}
                  />
                  <div className="snapshot-tile-copy">
                    <strong>{snapshot.caption || "Current mental state"}</strong>
                    <p>{snapshot.is_public ? "public share" : "private capture"}</p>
                  </div>
                </article>
              ))}
            </div>
          )}
        </div>

        <div className="drawer-section">
          <div className="drawer-label">weekly reports</div>
          <div className="drawer-actions-row">
            <button className="drawer-action" onClick={onGenerateReport} disabled={busy}>
              {busy ? "generating..." : "generate report"}
            </button>
          </div>
          {latestReport ? (
            <article className="report-card-inline">
              {latestReport.image_url ? <img src={latestReport.image_url} alt="Latest weekly report" /> : null}
              <div className="report-card-copy">
                <strong>
                  {latestReport.week_start} to {latestReport.week_end}
                </strong>
                <p>{reportSummary(latestReport)}</p>
              </div>
            </article>
          ) : (
            <div className="drawer-empty">generate your first weekly report.</div>
          )}
          {reports.length > 1 ? (
            <div className="report-list-compact">
              {reports.slice(1, 6).map((report) => (
                <div key={report.id} className="report-row">
                  <strong>{report.week_start}</strong>
                  <span>{reportSummary(report)}</span>
                </div>
              ))}
            </div>
          ) : null}
        </div>
      </aside>
    </>
  );
}

