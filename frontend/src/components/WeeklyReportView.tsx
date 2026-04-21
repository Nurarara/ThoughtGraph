import { ReportCard } from "./ReportCard";
import type { WeeklyReport } from "../types";

interface WeeklyReportViewProps {
  latestReport: WeeklyReport | null;
  reports: WeeklyReport[];
  onGenerate: () => Promise<WeeklyReport>;
  onOpen: (report: WeeklyReport) => void;
}

export function WeeklyReportView({ latestReport, reports, onGenerate, onOpen }: WeeklyReportViewProps) {
  return (
    <section className="page-grid">
      <section className="page-card">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Weekly</p>
            <h2>Your Mind This Week</h2>
          </div>
          <button className="primary-button" onClick={() => void onGenerate()}>
            Generate latest
          </button>
        </div>
        {latestReport ? (
          <>
            {latestReport.image_url ? <img className="report-image" src={latestReport.image_url} alt="Weekly report" /> : null}
            <p className="page-lede">{String(latestReport.content.summary ?? "")}</p>
          </>
        ) : (
          <p className="notification-empty">Generate the first weekly report to start the timeline.</p>
        )}
      </section>
      <section className="page-card">
        <div className="section-heading">
          <div>
            <p className="eyebrow">History</p>
            <h2>Recent reports</h2>
          </div>
        </div>
        <div className="report-list">
          {reports.map((report) => (
            <ReportCard key={report.id} report={report} onOpen={onOpen} />
          ))}
        </div>
      </section>
    </section>
  );
}
