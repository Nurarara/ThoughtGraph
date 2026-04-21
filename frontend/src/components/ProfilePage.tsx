import { InfluenceMap } from "./InfluenceMap";
import { SnapshotCard } from "./SnapshotCard";
import type { InfluenceScore, Snapshot, UserProfile } from "../types";

interface ProfilePageProps {
  profile: UserProfile | null;
  influence: InfluenceScore[];
  snapshots: Snapshot[];
  onOpenSnapshot: (snapshot: Snapshot) => void;
}

export function ProfilePage({ profile, influence, snapshots, onOpenSnapshot }: ProfilePageProps) {
  return (
    <section className="page-grid">
      <section className="page-card">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Profile</p>
            <h2>{profile?.display_name ?? "Profile"}</h2>
          </div>
        </div>
        <p className="page-lede">{profile?.bio || "No public bio yet."}</p>
        <div className="profile-stats">
          <span>{profile?.follower_count ?? 0} followers</span>
          <span>{profile?.following_count ?? 0} following</span>
          <span>{profile?.thought_count ?? 0} thoughts</span>
        </div>
      </section>
      <InfluenceMap influence={influence} />
      <section className="page-card">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Snapshots</p>
            <h2>Shareable moments</h2>
          </div>
        </div>
        <div className="snapshot-grid">
          {snapshots.map((snapshot) => (
            <SnapshotCard key={snapshot.id} snapshot={snapshot} onOpen={onOpenSnapshot} />
          ))}
        </div>
      </section>
    </section>
  );
}
