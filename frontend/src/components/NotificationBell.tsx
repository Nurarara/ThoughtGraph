import { useState } from "react";

import type { NotificationItem } from "../types";

interface NotificationBellProps {
  notifications: NotificationItem[];
  onRead: (notificationId: string) => Promise<void>;
}

export function NotificationBell({ notifications, onRead }: NotificationBellProps) {
  const [open, setOpen] = useState(false);
  const unreadCount = notifications.filter((item) => !item.read).length;

  return (
    <div className="notification-shell">
      <button className="ghost-button notification-button" onClick={() => setOpen((current) => !current)}>
        Inbox {unreadCount > 0 ? `(${unreadCount})` : ""}
      </button>
      {open ? (
        <div className="notification-dropdown">
          {notifications.length === 0 ? (
            <p className="notification-empty">No social notifications yet.</p>
          ) : (
            notifications.slice(0, 6).map((notification) => (
              <button
                key={notification.id}
                className={`notification-item ${notification.read ? "" : "unread"}`}
                onClick={() => void onRead(notification.id)}
              >
                <strong>{notification.actor_display_name ?? "ThoughtGraph"}</strong>
                <span>{notification.content}</span>
              </button>
            ))
          )}
        </div>
      ) : null}
    </div>
  );
}

