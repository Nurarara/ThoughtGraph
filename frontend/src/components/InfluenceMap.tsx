import type { InfluenceScore } from "../types";

interface InfluenceMapProps {
  influence: InfluenceScore[];
}

export function InfluenceMap({ influence }: InfluenceMapProps) {
  return (
    <section className="page-card">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Influence Map</p>
          <h2>Who is bending your graph</h2>
        </div>
      </div>
      <div className="influence-list">
        {influence.length === 0 ? <p className="notification-empty">Influence scores appear once you follow or reply to someone.</p> : null}
        {influence.map((item) => (
          <article key={item.target_user_id} className="influence-row">
            <div>
              <strong>{item.target_display_name}</strong>
              <p>{item.summary}</p>
            </div>
            <div className="influence-meter">
              <span style={{ width: `${Math.max(10, item.score * 100)}%` }} />
              <small>{Math.round(item.score * 100)}%</small>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
