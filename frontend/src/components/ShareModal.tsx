import type { Snapshot, WeeklyReport } from "../types";

interface ShareModalProps {
  item: Snapshot | WeeklyReport | null;
  onClose: () => void;
}

export function ShareModal({ item, onClose }: ShareModalProps) {
  if (!item) {
    return null;
  }

  const imageUrl = "image_url" in item ? item.image_url : null;

  return (
    <div className="share-modal-backdrop" onClick={onClose}>
      <div className="share-modal" onClick={(event) => event.stopPropagation()}>
        <div className="detail-header">
          <div>
            <p className="eyebrow">Share</p>
            <h3>Snapshot or report</h3>
          </div>
          <button className="ghost-button" onClick={onClose}>
            Close
          </button>
        </div>
        {imageUrl ? <img className="share-preview" src={imageUrl} alt="Share preview" /> : null}
        <p className="notification-empty">This local-first build uses the generated image directly. In production this would hand off a share URL.</p>
      </div>
    </div>
  );
}
