import { FollowButton } from "./FollowButton";
import type { InfluenceScore, NotificationItem, SocialFeedItem, UserProfile, UserSearchResult } from "../types";

interface SocialSidebarProps {
  me: UserProfile | null;
  users: UserSearchResult[];
  notifications: NotificationItem[];
  influence: InfluenceScore[];
  feed: SocialFeedItem[];
  socialViewEnabled: boolean;
  onToggleSocialView: () => void;
  onToggleFollow: (userId: string, following: boolean) => Promise<void>;
  onSeedNetwork: () => Promise<void>;
  loading: boolean;
}

export function SocialSidebar({
  me,
  users,
  notifications,
  influence,
  feed,
  socialViewEnabled,
  onToggleSocialView,
  onToggleFollow,
  onSeedNetwork,
  loading,
}: SocialSidebarProps) {
  return (
    <aside className="sidebar-panel social-panel">
      <div className="sidebar-section">
        <div className="sidebar-heading compact">
          <div>
            <p className="eyebrow">Social Layer</p>
            <h3>Profiles, follows, and network context</h3>
          </div>
          <button className={`ghost-button ${socialViewEnabled ? "active-toggle" : ""}`} onClick={onToggleSocialView}>
            {socialViewEnabled ? "Social on" : "Social off"}
          </button>
        </div>

        {me ? (
          <div className="profile-card">
            <div>
              <p className="profile-name">{me.display_name}</p>
              <p className="profile-bio">{me.bio || "Your default local profile. V2 now treats this as a public-facing identity layer."}</p>
            </div>
            <div className="profile-stats">
              <span>{me.follower_count} followers</span>
              <span>{me.following_count} following</span>
              <span>{me.thought_count} thoughts</span>
            </div>
          </div>
        ) : null}
      </div>

      <div className="sidebar-section">
        <div className="sidebar-heading compact">
          <div>
            <p className="eyebrow">Discover</p>
            <h3>Public minds worth connecting to</h3>
          </div>
        </div>

        {users.length === 0 && !loading ? (
          <div className="empty-panel">
            <p>The social graph is empty. Load the demo network to explore follows and opt-in social graph overlays.</p>
            <button className="primary-button" onClick={() => void onSeedNetwork()}>
              Load demo network
            </button>
          </div>
        ) : (
          <div className="user-list">
            {users.slice(0, 5).map((user) => (
              <div key={user.id} className="user-row">
                <div className="user-copy">
                  <strong>{user.display_name}</strong>
                  <small>{user.top_clusters.join(" · ") || "General reflection"}</small>
                  <span>{user.bio}</span>
                </div>
                <FollowButton following={user.relationship_following} onToggle={() => onToggleFollow(user.id, user.relationship_following)} />
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="sidebar-section">
        <div className="sidebar-heading compact">
          <div>
            <p className="eyebrow">Recent Activity</p>
            <h3>Network signals</h3>
          </div>
        </div>
        <div className="notification-preview-list">
          {notifications.slice(0, 3).map((notification) => (
            <div key={notification.id} className={`notification-preview ${notification.read ? "" : "unread"}`}>
              <strong>{notification.actor_display_name ?? "ThoughtGraph"}</strong>
              <span>{notification.content}</span>
            </div>
          ))}
          {notifications.length === 0 ? <p className="notification-empty">Follow activity and replies will appear here.</p> : null}
        </div>
      </div>

      <div className="sidebar-section">
        <div className="sidebar-heading compact">
          <div>
            <p className="eyebrow">Influence</p>
            <h3>Who currently shapes you</h3>
          </div>
        </div>
        <div className="micro-list">
          {influence.slice(0, 3).map((item) => (
            <div key={item.target_user_id} className="micro-row">
              <strong>{item.target_display_name}</strong>
              <small>{Math.round(item.score * 100)}% influence</small>
            </div>
          ))}
          {influence.length === 0 ? <p className="notification-empty">Influence becomes visible once your graph interacts with others.</p> : null}
        </div>
      </div>

      <div className="sidebar-section">
        <div className="sidebar-heading compact">
          <div>
            <p className="eyebrow">Feed</p>
            <h3>What followed users are saying</h3>
          </div>
        </div>
        <div className="micro-list">
          {feed.slice(0, 3).map((item) => (
            <div key={item.thought.id} className="micro-row">
              <strong>{item.thought.author_display_name}</strong>
              <small>{item.thought.content}</small>
            </div>
          ))}
          {feed.length === 0 ? <p className="notification-empty">Follow a few people to turn on the social feed.</p> : null}
        </div>
      </div>
    </aside>
  );
}
