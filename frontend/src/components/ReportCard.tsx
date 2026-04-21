import type { WeeklyReport } from "../types";

interface ReportCardProps {
  report: WeeklyReport;
  onOpen: (report: WeeklyReport) => void;
}

export function ReportCard({ report, onOpen }: ReportCardProps) {
  return (
    <article className="report-card">
      <div>
        <strong>
          {report.week_start} - {report.week_end}
        </strong>
        <p>{String(report.content.summary ?? "Weekly report")}</p>
      </div>
      <button className="ghost-button" onClick={() => onOpen(report)}>
        View report
      </button>
    </article>
  );
}
