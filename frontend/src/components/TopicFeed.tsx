import { FormEvent, useCallback, useEffect, useState } from "react";

import { thoughtApi } from "../lib/apiClient";
import type { ClusterKey, CommentRead, PostRead } from "../lib/apiClient";

interface Props {
  open: boolean;
  cluster: ClusterKey | null;
  currentUserId: string | null;
  onClose: () => void;
  onCompose: (cluster: ClusterKey) => void;
  onOpenProfile?: (userId: string) => void;
}

const CLUSTER_LABELS: Record<ClusterKey, { label: string; hex: string }> = {
  technology: { label: "Technology", hex: "#7a9bb5" },
  growth: { label: "Growth", hex: "#9b8abf" },
  purpose: { label: "Purpose", hex: "#c4a062" },
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

export function TopicFeed({
  open,
  cluster,
  currentUserId,
  onClose,
  onCompose,
  onOpenProfile,
}: Props) {
  const [posts, setPosts] = useState<PostRead[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [expandedPostId, setExpandedPostId] = useState<string | null>(null);
  const [commentsByPost, setCommentsByPost] = useState<Record<string, CommentRead[]>>({});
  const [commentDrafts, setCommentDrafts] = useState<Record<string, string>>({});

  const refresh = useCallback(async () => {
    if (!cluster) return;
    setLoading(true);
    setError(null);
    try {
      const response = await thoughtApi.getClusterFeed(cluster);
      setPosts(response.posts);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, [cluster]);

  useEffect(() => {
    if (open && cluster) refresh();
  }, [open, cluster, refresh]);

  useEffect(() => {
    if (!open) {
      setExpandedPostId(null);
      setCommentsByPost({});
      setCommentDrafts({});
    }
  }, [open]);

  const handleDelete = async (postId: string) => {
    try {
      await thoughtApi.deletePost(postId);
      setPosts((prev) => prev.filter((p) => p.id !== postId));
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const handleReact = async (postId: string) => {
    try {
      const result = await thoughtApi.reactToPost(postId);
      setPosts((prev) =>
        prev.map((p) =>
          p.id === postId
            ? { ...p, reaction_count: result.reaction_count, viewer_liked: result.liked }
            : p,
        ),
      );
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const toggleComments = async (postId: string) => {
    if (expandedPostId === postId) {
      setExpandedPostId(null);
      return;
    }
    setExpandedPostId(postId);
    if (!commentsByPost[postId]) {
      try {
        const response = await thoughtApi.getComments(postId);
        setCommentsByPost((prev) => ({ ...prev, [postId]: response.comments }));
      } catch (err) {
        setError((err as Error).message);
      }
    }
  };

  const handleAddComment = async (event: FormEvent, postId: string) => {
    event.preventDefault();
    const draft = (commentDrafts[postId] ?? "").trim();
    if (!draft) return;
    try {
      const comment = await thoughtApi.addComment(postId, draft);
      setCommentsByPost((prev) => ({
        ...prev,
        [postId]: [...(prev[postId] ?? []), comment],
      }));
      setCommentDrafts((prev) => ({ ...prev, [postId]: "" }));
      setPosts((prev) =>
        prev.map((p) =>
          p.id === postId ? { ...p, comment_count: p.comment_count + 1 } : p,
        ),
      );
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const handleDeleteComment = async (postId: string, commentId: string) => {
    try {
      await thoughtApi.deleteComment(commentId);
      setCommentsByPost((prev) => ({
        ...prev,
        [postId]: (prev[postId] ?? []).filter((c) => c.id !== commentId),
      }));
      setPosts((prev) =>
        prev.map((p) =>
          p.id === postId
            ? { ...p, comment_count: Math.max(0, p.comment_count - 1) }
            : p,
        ),
      );
    } catch (err) {
      setError((err as Error).message);
    }
  };

  if (!cluster) return null;
  const meta = CLUSTER_LABELS[cluster];

  return (
    <>
      <div className={`sheet-backdrop ${open ? "visible" : ""}`} onClick={onClose} />
      <section className={`sheet ${open ? "open" : ""}`} style={{ borderTopColor: meta.hex }}>
        <div className="sheet-handle" />
        <div className="sheet-header">
          <div>
            <div className="sheet-title" style={{ color: meta.hex }}>
              {meta.label}
            </div>
            <div className="sheet-sub">topic feed · friends & public</div>
          </div>
          <div className="sheet-actions">
            <button
              className="sheet-action"
              style={{ borderColor: meta.hex, color: meta.hex }}
              onClick={() => onCompose(cluster)}
            >
              + share
            </button>
            <button className="sheet-close" onClick={onClose}>
              ×
            </button>
          </div>
        </div>

        <div className="sheet-body">
          {loading ? <div className="sheet-empty">loading…</div> : null}
          {!loading && posts.length === 0 ? (
            <div className="sheet-empty">
              no posts yet. be the first to share something in {meta.label.toLowerCase()}.
            </div>
          ) : null}
          <ul className="sheet-list">
            {posts.map((post) => {
              const isMine = post.user_id === currentUserId;
              const expanded = expandedPostId === post.id;
              const comments = commentsByPost[post.id] ?? [];
              return (
                <li key={post.id} className="sheet-post">
                  {post.media_url ? (
                    <div className="sheet-post-media">
                      <img
                        src={post.media_url}
                        alt=""
                        onError={(e) => (e.currentTarget.style.display = "none")}
                      />
                    </div>
                  ) : null}
                  <div className="sheet-post-body">
                    <div className="sheet-post-meta">
                      <button
                        className="sheet-post-author-button"
                        onClick={() => onOpenProfile?.(post.user_id)}
                        disabled={!onOpenProfile}
                      >
                        {post.display_name}
                      </button>
                      <span className="sheet-post-dot">·</span>
                      <span className="sheet-post-time">{relativeTime(post.created_at)}</span>
                      {post.visibility !== "public" ? (
                        <>
                          <span className="sheet-post-dot">·</span>
                          <span className="sheet-post-visibility">{post.visibility}</span>
                        </>
                      ) : null}
                      {post.location ? (
                        <>
                          <span className="sheet-post-dot">·</span>
                          <span className="sheet-post-location">{post.location}</span>
                        </>
                      ) : null}
                    </div>
                    <div className="sheet-post-caption">{post.caption}</div>

                    <div className="sheet-post-engagement">
                      <button
                        className={`engagement-button ${post.viewer_liked ? "active" : ""}`}
                        onClick={() => handleReact(post.id)}
                        style={post.viewer_liked ? { color: meta.hex, borderColor: meta.hex } : undefined}
                      >
                        {post.viewer_liked ? "♥" : "♡"} {post.reaction_count}
                      </button>
                      <button
                        className={`engagement-button ${expanded ? "active" : ""}`}
                        onClick={() => toggleComments(post.id)}
                      >
                        ◌ {post.comment_count}
                      </button>
                      {isMine ? (
                        <button
                          className="engagement-button ghost"
                          onClick={() => handleDelete(post.id)}
                        >
                          delete
                        </button>
                      ) : null}
                    </div>

                    {expanded ? (
                      <div className="comment-thread">
                        {comments.length === 0 ? (
                          <div className="comment-empty">no comments yet</div>
                        ) : (
                          <ul className="comment-list">
                            {comments.map((c) => (
                              <li key={c.id} className="comment-item">
                                <span className="comment-author">{c.display_name}</span>
                                <span className="comment-body">{c.content}</span>
                                <span className="comment-time">{relativeTime(c.created_at)}</span>
                                {c.user_id === currentUserId ? (
                                  <button
                                    className="comment-delete"
                                    onClick={() => handleDeleteComment(post.id, c.id)}
                                  >
                                    remove
                                  </button>
                                ) : null}
                              </li>
                            ))}
                          </ul>
                        )}
                        {currentUserId ? (
                          <form
                            className="comment-form"
                            onSubmit={(e) => handleAddComment(e, post.id)}
                          >
                            <input
                              className="comment-input"
                              placeholder="add a comment…"
                              value={commentDrafts[post.id] ?? ""}
                              onChange={(e) =>
                                setCommentDrafts((prev) => ({
                                  ...prev,
                                  [post.id]: e.currentTarget.value,
                                }))
                              }
                              maxLength={500}
                            />
                            <button className="comment-submit" type="submit">
                              send
                            </button>
                          </form>
                        ) : null}
                      </div>
                    ) : null}
                  </div>
                </li>
              );
            })}
          </ul>
        </div>

        {error ? <div className="sheet-error">{error}</div> : null}
      </section>
    </>
  );
}
