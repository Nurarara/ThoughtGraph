import { FormEvent, useState } from "react";

import { thoughtApi } from "../lib/apiClient";
import type { ClusterKey, PostVisibility } from "../lib/apiClient";

const CLUSTER_OPTIONS: { value: ClusterKey; label: string; hex: string }[] = [
  { value: "technology", label: "Technology", hex: "#7a9bb5" },
  { value: "growth", label: "Growth", hex: "#9b8abf" },
  { value: "purpose", label: "Purpose", hex: "#c4a062" },
];

const VISIBILITY_OPTIONS: { value: PostVisibility; label: string }[] = [
  { value: "friends", label: "friends only" },
  { value: "public", label: "public" },
  { value: "private", label: "only me" },
];

interface Props {
  open: boolean;
  initialCluster?: ClusterKey;
  onClose: () => void;
  onCreated?: () => void;
}

export function PostComposer({ open, initialCluster, onClose, onCreated }: Props) {
  const [cluster, setCluster] = useState<ClusterKey>(initialCluster ?? "technology");
  const [caption, setCaption] = useState("");
  const [mediaUrl, setMediaUrl] = useState("");
  const [location, setLocation] = useState("");
  const [visibility, setVisibility] = useState<PostVisibility>("friends");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await thoughtApi.createPost({
        cluster_key: cluster,
        caption: caption.trim(),
        media_url: mediaUrl.trim() || null,
        location: location.trim() || null,
        visibility,
      });
      setCaption("");
      setMediaUrl("");
      setLocation("");
      onCreated?.();
      onClose();
    } catch (err) {
      setError((err as Error).message || "could not post");
    } finally {
      setBusy(false);
    }
  };

  if (!open) return null;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-title">share to a topic</div>
        <form className="modal-form" onSubmit={handleSubmit}>
          <div className="modal-field">
            <label className="modal-label">topic</label>
            <div className="modal-cluster-row">
              {CLUSTER_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  className={`modal-cluster ${cluster === opt.value ? "selected" : ""}`}
                  style={{
                    borderColor: opt.hex,
                    color: cluster === opt.value ? opt.hex : undefined,
                  }}
                  onClick={() => setCluster(opt.value)}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          <div className="modal-field">
            <label className="modal-label">caption</label>
            <textarea
              className="modal-textarea"
              rows={3}
              placeholder="a thought, moment, or link…"
              value={caption}
              onChange={(e) => setCaption(e.currentTarget.value)}
              maxLength={500}
              required
            />
          </div>

          <div className="modal-field">
            <label className="modal-label">image url (optional)</label>
            <input
              className="modal-input"
              placeholder="https://…"
              value={mediaUrl}
              onChange={(e) => setMediaUrl(e.currentTarget.value)}
            />
          </div>

          <div className="modal-field">
            <label className="modal-label">location (optional)</label>
            <input
              className="modal-input"
              placeholder="brooklyn · rooftop"
              value={location}
              onChange={(e) => setLocation(e.currentTarget.value)}
              maxLength={200}
            />
          </div>

          <div className="modal-field">
            <label className="modal-label">visible to</label>
            <select
              className="modal-input"
              value={visibility}
              onChange={(e) => setVisibility(e.currentTarget.value as PostVisibility)}
            >
              {VISIBILITY_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {error ? <div className="modal-error">{error}</div> : null}

          <div className="modal-actions">
            <button type="button" className="modal-secondary" onClick={onClose}>
              cancel
            </button>
            <button type="submit" className="modal-submit" disabled={busy}>
              {busy ? "posting…" : "share"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
