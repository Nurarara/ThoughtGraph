import { useCallback, useEffect, useRef, useState } from "react";

import { thoughtApi } from "../lib/apiClient";
import type { NotificationItem } from "../lib/apiClient";

const LABEL_BY_TYPE: Record<string, (actor: string) => string> = {
  friend_request: (a) => `${a} wants to connect`,
  friend_accept: (a) => `${a} accepted your request`,
  post_reaction: (a) => `${a} reacted to your post`,
  post_comment: (a) => `${a} commented on your post`,
  reply: (a) => `${a} replied to your thought`,
  new_follower: (a) => `${a} started following you`,
};

interface Props {
  onOpenProfile?: (userId: string) => void;
}

function relTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const sec = Math.floor(diff / 1000);
  if (sec < 60) return "just now";
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h`;
  const day = Math.floor(hr / 24);
  return `${day}d`;
}

export function NotificationsBell({ onOpenProfile }: Props) {
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [open, setOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await thoughtApi.getNotifications();
      setItems(data);
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 20_000);
    return () => clearInterval(id);
  }, [refresh]);

  useEffect(() => {
    if (!open) return;
    const onDocClick = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [open]);

  const unread = items.filter((n) => !n.read).length;

  const handleMarkAll = async () => {
    const promises = items
      .filter((n) => !n.read)
      .map((n) => thoughtApi.markNotificationRead(n.id, true).catch(() => null));
    await Promise.all(promises);
    refresh();
  };

  const handleClickItem = async (n: NotificationItem) => {
    if (!n.read) {
      await thoughtApi.markNotificationRead(n.id, true).catch(() => null);
    }
    if (n.actor_id && onOpenProfile) {
      onOpenProfile(n.actor_id);
      setOpen(false);
    }
    refresh();
  };

  return (
    <div className="bell-wrap" ref={dropdownRef}>
      <button
        className="topbar-button bell-button"
        onClick={() => setOpen((prev) => !prev)}
        title="notifications"
      >
        <span className="bell-icon">◉</span>
        {unread > 0 ? <span className="bell-badge">{unread > 9 ? "9+" : unread}</span> : null}
      </button>
      {open ? (
        <div className="bell-dropdown">
          <div className="bell-header">
            <span>notifications</span>
            {unread > 0 ? (
              <button className="bell-mark-all" onClick={handleMarkAll}>
                mark all read
              </button>
            ) : null}
          </div>
          {items.length === 0 ? (
            <div className="bell-empty">no activity yet</div>
          ) : (
            <ul className="bell-list">
              {items.slice(0, 30).map((n) => {
                const actor = n.actor_display_name ?? "someone";
                const label = LABEL_BY_TYPE[n.type]?.(actor) ?? `${actor} · ${n.type}`;
                return (
                  <li
                    key={n.id}
                    className={`bell-item ${n.read ? "read" : "unread"}`}
                    onClick={() => handleClickItem(n)}
                  >
                    <div className="bell-item-text">{label}</div>
                    <div className="bell-item-time">{relTime(n.created_at)}</div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      ) : null}
    </div>
  );
}
