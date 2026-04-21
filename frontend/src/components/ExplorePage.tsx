import { SnapshotCard } from "./SnapshotCard";
import type { Snapshot, SocialFeedItem, SuggestedUser, TrendingCluster } from "../types";

interface ExplorePageProps {
  trendingClusters: TrendingCluster[];
  suggestedUsers: SuggestedUser[];
  recentPublicSnapshots: Snapshot[];
  feed: SocialFeedItem[];
  onFollow: (userId: string) => Promise<void>;
  onOpenSnapshot: (snapshot: Snapshot) => void;
}

export function ExplorePage({
  trendingClusters,
  suggestedUsers,
  recentPublicSnapshots,
  feed,
  onFollow,
  onOpenSnapshot,
}: ExplorePageProps) {
  return (
    <section className="page-grid">
      <section className="page-card">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Explore</p>
            <h2>Trending clusters</h2>
          </div>
        </div>
        <div className="cluster-list">
          {trendingClusters.map((cluster) => (
            <article key={cluster.label} className="cluster-card">
              <strong>{cluster.label}</strong>
              <small>{cluster.growth_percentage}% growth • {cluster.user_count} minds</small>
              <p>{cluster.sample_thoughts[0]}</p>
            </article>
          ))}
        </div>
      </section>
      <section className="page-card">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Suggested</p>
            <h2>Minds near yours</h2>
          </div>
        </div>
        <div className="user-list">
          {suggestedUsers.map((user) => (
            <article key={user.user_id} className="user-row">
              <div className="user-copy">
                <strong>{user.display_name}</strong>
                <small>{user.top_clusters.join(" • ") || "General reflection"}</small>
              </div>
              <button className="follow-button" onClick={() => void onFollow(user.user_id)}>
                Follow
              </button>
            </article>
          ))}
        </div>
      </section>
      <section className="page-card">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Public snapshots</p>
            <h2>Shared neural states</h2>
          </div>
        </div>
        <div className="snapshot-grid">
          {recentPublicSnapshots.map((snapshot) => (
            <SnapshotCard key={snapshot.id} snapshot={snapshot} onOpen={onOpenSnapshot} />
          ))}
        </div>
      </section>
      <section className="page-card">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Feed</p>
            <h2>Recent public thoughts</h2>
          </div>
        </div>
        <div className="feed-list">
          {feed.map((item) => (
            <article key={item.thought.id} className="feed-item">
              <strong>{item.thought.author_display_name}</strong>
              <p>{item.thought.content}</p>
              <small>{item.relationship}</small>
            </article>
          ))}
        </div>
      </section>
    </section>
  );
}
