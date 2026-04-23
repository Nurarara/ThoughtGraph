import type {
  ClusterKey,
  SerendipityResponse,
  SnapshotRead,
  TrendingCluster,
} from "../lib/apiClient";

interface ExploreDrawerProps {
  open: boolean;
  trending: TrendingCluster[];
  publicSnapshots: SnapshotRead[];
  serendipity: SerendipityResponse | null;
  busy: boolean;
  onClose: () => void;
  onToggleSerendipity: (enabled: boolean) => void;
  onOpenFeed: (cluster: ClusterKey) => void;
}

const CLUSTER_MAP: Record<string, ClusterKey> = {
  technology: "technology",
  growth: "growth",
  purpose: "purpose",
};

function inferCluster(label: string, samples: string[]): ClusterKey | null {
  const haystack = `${label} ${samples.join(" ")}`.toLowerCase();
  if (haystack.includes("tech") || haystack.includes("ai") || haystack.includes("system")) {
    return "technology";
  }
  if (haystack.includes("grow") || haystack.includes("learn") || haystack.includes("discipline")) {
    return "growth";
  }
  if (haystack.includes("purpose") || haystack.includes("meaning") || haystack.includes("identity")) {
    return "purpose";
  }
  return null;
}

export function ExploreDrawer({
  open,
  trending,
  publicSnapshots,
  serendipity,
  busy,
  onClose,
  onToggleSerendipity,
  onOpenFeed,
}: ExploreDrawerProps) {
  return (
    <>
      <div className={`drawer-backdrop ${open ? "visible" : ""}`} onClick={onClose} />
      <aside className={`drawer drawer-wide ${open ? "open" : ""}`}>
        <div className="drawer-header">
          <div className="drawer-title">explore</div>
          <button className="drawer-close" onClick={onClose}>
            x
          </button>
        </div>

        <div className="drawer-section">
          <div className="drawer-label">serendipity</div>
          <label className="drawer-toggle">
            <span>anonymous resonance</span>
            <input
              type="checkbox"
              checked={Boolean(serendipity?.enabled)}
              onChange={(event) => onToggleSerendipity(event.currentTarget.checked)}
              disabled={busy}
            />
          </label>
          <div className="drawer-copy">
            Opt in to see strangers thinking along similar lines to your latest thought.
          </div>
          {serendipity?.enabled && serendipity.matches.length === 0 ? (
            <div className="drawer-empty">
              no live strangers yet{serendipity.latest_thought_preview ? ` for "${serendipity.latest_thought_preview}"` : ""}.
            </div>
          ) : null}
          {serendipity?.matches.length ? (
            <div className="explore-card-list">
              {serendipity.matches.map((match) => (
                <article key={match.id} className="explore-card">
                  <div className="explore-card-header">
                    <strong>{match.alias}</strong>
                    <span>{match.similarity_score}% resonance</span>
                  </div>
                  <p>{match.thought_preview}</p>
                  {match.shared_topics.length > 0 ? (
                    <div className="explore-tags">
                      {match.shared_topics.map((topic) => (
                        <span key={topic}>{topic}</span>
                      ))}
                    </div>
                  ) : null}
                </article>
              ))}
            </div>
          ) : null}
        </div>

        <div className="drawer-section">
          <div className="drawer-label">trending clusters</div>
          <div className="explore-card-list">
            {trending.slice(0, 6).map((cluster) => {
              const clusterKey = inferCluster(cluster.label, cluster.sample_thoughts);
              return (
                <article key={cluster.label} className="explore-card">
                  <div className="explore-card-header">
                    <strong>{cluster.label}</strong>
                    <span>{cluster.growth_percentage.toFixed(0)}%</span>
                  </div>
                  <p>{cluster.user_count} minds, {cluster.thought_count} thoughts</p>
                  {cluster.sample_thoughts.length > 0 ? (
                    <div className="drawer-copy">{cluster.sample_thoughts[0]}</div>
                  ) : null}
                  {clusterKey ? (
                    <button className="drawer-action" onClick={() => onOpenFeed(CLUSTER_MAP[clusterKey])}>
                      open topic feed
                    </button>
                  ) : null}
                </article>
              );
            })}
          </div>
        </div>

        <div className="drawer-section">
          <div className="drawer-label">public snapshots</div>
          {publicSnapshots.length === 0 ? (
            <div className="drawer-empty">no public snapshots yet</div>
          ) : (
            <div className="snapshot-grid compact">
              {publicSnapshots.slice(0, 6).map((snapshot) => (
                <article key={snapshot.id} className="snapshot-tile">
                  <img
                    src={snapshot.thumbnail_url ?? snapshot.image_url}
                    alt={snapshot.caption || "Public ThoughtGraph snapshot"}
                  />
                  <div className="snapshot-tile-copy">
                    <strong>{snapshot.user_display_name}</strong>
                    <p>{snapshot.caption || "Current mental state"}</p>
                  </div>
                </article>
              ))}
            </div>
          )}
        </div>
      </aside>
    </>
  );
}

