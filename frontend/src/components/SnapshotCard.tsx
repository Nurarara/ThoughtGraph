import type { Snapshot } from "../types";

interface SnapshotCardProps {
  snapshot: Snapshot;
  onOpen?: (snapshot: Snapshot) => void;
}

export function SnapshotCard({ snapshot, onOpen }: SnapshotCardProps) {
  return (
    <article className="snapshot-card">
      <img src={snapshot.thumbnail_url ?? snapshot.image_url} alt={snapshot.caption || "ThoughtGraph snapshot"} />
      <div className="snapshot-copy">
        <strong>{snapshot.user_display_name}</strong>
        <p>{snapshot.caption || "Captured state of mind"}</p>
        <button className="ghost-button" onClick={() => onOpen?.(snapshot)}>
          Open snapshot
        </button>
      </div>
    </article>
  );
}
