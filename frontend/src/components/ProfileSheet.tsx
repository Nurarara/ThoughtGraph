import { useEffect, useState } from "react";

import { thoughtApi } from "../lib/apiClient";
import type { ClusterKey, ProfileSummary } from "../lib/apiClient";

interface Props {
  userId: string | null;
  onClose: () => void;
  onFriendsChanged?: () => void;
}

const CLUSTER_HEX: Record<ClusterKey, string> = {
  technology: "#7a9bb5",
  growth: "#9b8abf",
  purpose: "#c4a062",
};

function relativeTime(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  const sec = Math.floor(ms / 1000);
  if (sec < 60) return "just now";
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.floor(hr / 24);
  return `${day}d ago`;
}

export function ProfileSheet({ userId, onClose, onFriendsChanged }: Props) {
  const [summary, setSummary] = useState<ProfileSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!userId) {
      setSummary(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    thoughtApi
      .getProfileSummary(userId)
      .then((data) => {
        if (!cancelled) setSummary(data);
      })
      .catch((err) => {
        if (!cancelled) setError((err as Error).message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [userId]);

  const handleConnect = async () => {
    if (!summary) return;
    setBusy(true);
    try {
      await thoughtApi.requestFriend(summary.id);
      setSummary({ ...summary, friend_status: "outgoing" });
      onFriendsChanged?.();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const handleAccept = async () => {
    if (!summary) return;
    setBusy(true);
    try {
      await thoughtApi.acceptFriend(summary.id);
      setSummary({ ...summary, friend_status: "friends" });
      onFriendsChanged?.();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const open = userId !== null;
  const initial = summary?.display_name?.[0]?.toUpperCase() ?? "·";

  return (
    <>
      <div
        className={`profile-backdrop ${open ? "visible" : ""}`}
        onClick={onClose}
      />
      <section className={`profile-sheet ${open ? "open" : ""}`}>
        <div className="profile-close-row">
          <button className="profile-close" onClick={onClose}>
            ×
          </button>
        </div>

        {loading ? <div className="profile-empty">loading profile…</div> : null}

        {summary ? (
          <>
            <div className="profile-head">
              <div className="profile-avatar">
                {summary.avatar_url ? (
                  <img src={summary.avatar_url} alt="" />
                ) : (
                  <span>{initial}</span>
                )}
              </div>
              <div className="profile-head-info">
                <div className="profile-name">{summary.display_name}</div>
                {summary.bio ? (
                  <div className="profile-bio">{summary.bio}</div>
                ) : null}
                <div className="profile-stats">
                  <span>{summary.public_post_count} posts</span>
                  {!summary.is_self ? (
                    <span>· {summary.mutual_friend_count} mutual</span>
                  ) : null}
                </div>
              </div>
            </div>

            {summary.top_clusters.length > 0 ? (
              <div className="profile-clusters">
                {summary.top_clusters.map((c) => (
                  <span key={c} className="profile-cluster-chip">
                    {c}
                  </span>
                ))}
              </div>
            ) : null}

            {!summary.is_self && summary.resonance_score !== undefined && summary.resonance_score !== null ? (
              <div className="profile-resonance">
                <div className="profile-resonance-score">{summary.resonance_score}</div>
                <div className="profile-resonance-copy">
                  <strong>resonance</strong>
                  {summary.shared_topics && summary.shared_topics.length > 0 ? (
                    <span>{summary.shared_topics.join(" · ")}</span>
                  ) : (
                    <span>no clear shared themes yet</span>
                  )}
                </div>
              </div>
            ) : null}

            {!summary.is_self ? (
              <div className="profile-actions">
                {summary.friend_status === "friends" ? (
                  <button className="profile-action friend" disabled>
                    connected
                  </button>
                ) : null}
                {summary.friend_status === "outgoing" ? (
                  <button className="profile-action pending" disabled>
                    request sent
                  </button>
                ) : null}
                {summary.friend_status === "incoming" ? (
                  <button
                    className="profile-action"
                    onClick={handleAccept}
                    disabled={busy}
                  >
                    accept request
                  </button>
                ) : null}
                {summary.friend_status === "none" ||
                summary.friend_status === "declined" ? (
                  <button
                    className="profile-action"
                    onClick={handleConnect}
                    disabled={busy}
                  >
                    connect
                  </button>
                ) : null}
              </div>
            ) : null}

            <div className="profile-posts-heading">recent posts</div>
            {summary.recent_posts.length === 0 ? (
              <div className="profile-empty">nothing shared yet</div>
            ) : (
              <ul className="profile-posts">
                {summary.recent_posts.map((post) => {
                  const hex = CLUSTER_HEX[post.cluster_key];
                  return (
                    <li
                      key={post.id}
                      className="profile-post"
                      style={{ borderLeftColor: hex }}
                    >
                      {post.media_url ? (
                        <div className="profile-post-media">
                          <img
                            src={post.media_url}
                            alt=""
                            onError={(e) =>
                              (e.currentTarget.style.display = "none")
                            }
                          />
                        </div>
                      ) : null}
                      <div className="profile-post-body">
                        <div className="profile-post-caption">
                          {post.caption}
                        </div>
                        <div className="profile-post-meta">
                          <span style={{ color: hex }}>{post.cluster_key}</span>
                          <span>· {relativeTime(post.created_at)}</span>
                          {post.location ? <span>· {post.location}</span> : null}
                        </div>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </>
        ) : null}

        {error ? <div className="profile-error">{error}</div> : null}
      </section>
    </>
  );
}
