const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const API_PREFIX = `${API_URL}/api`;
const TOKEN_KEY = "thoughtgraph:session";

export interface SessionPayload {
  session_token: string;
  user_id: string;
  display_name: string;
  email: string;
  is_new_user: boolean;
}

export function loadSession(): SessionPayload | null {
  try {
    const raw = localStorage.getItem(TOKEN_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as SessionPayload;
  } catch {
    return null;
  }
}

export function saveSession(payload: SessionPayload) {
  localStorage.setItem(TOKEN_KEY, JSON.stringify(payload));
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const session = loadSession();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string> | undefined),
  };
  if (session?.session_token) {
    headers["Authorization"] = `Bearer ${session.session_token}`;
  }
  const response = await fetch(`${API_PREFIX}${path}`, { ...init, headers });
  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new Error(text || `request failed ${response.status}`);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export interface MagicLinkResponse {
  email: string;
  magic_link: string | null;
  expires_in_seconds: number;
}

export interface FriendSummary {
  id: string;
  display_name: string;
  avatar_url: string | null;
  bio: string;
  top_clusters: string[];
  status: string;
  since: string | null;
  resonance_score?: number | null;
  shared_topics?: string[];
}

export interface FriendsListResponse {
  friends: FriendSummary[];
  incoming: FriendSummary[];
  outgoing: FriendSummary[];
}

export type ClusterKey = "technology" | "growth" | "purpose";
export type PostVisibility = "public" | "friends" | "private";

export interface PostRead {
  id: string;
  user_id: string;
  display_name: string;
  cluster_key: ClusterKey;
  caption: string;
  media_url: string | null;
  location: string | null;
  visibility: PostVisibility;
  created_at: string;
  reaction_count: number;
  viewer_liked: boolean;
  comment_count: number;
}

export interface CommentRead {
  id: string;
  post_id: string;
  user_id: string;
  display_name: string;
  content: string;
  created_at: string;
}

export interface ReactionToggleResponse {
  post_id: string;
  liked: boolean;
  reaction_count: number;
}

export interface NotificationItem {
  id: string;
  type: string;
  actor_id: string | null;
  actor_display_name: string | null;
  thought_id: string | null;
  content: string;
  read: boolean;
  created_at: string;
}

export interface ProfileSummaryPost {
  id: string;
  cluster_key: ClusterKey;
  caption: string;
  media_url: string | null;
  location: string | null;
  created_at: string;
}

export interface ProfileSummary {
  id: string;
  display_name: string;
  bio: string;
  avatar_url: string | null;
  top_clusters: string[];
  friend_status: "self" | "friends" | "outgoing" | "incoming" | "none" | "declined";
  mutual_friend_count: number;
  public_post_count: number;
  resonance_score?: number | null;
  shared_topics?: string[];
  recent_posts: ProfileSummaryPost[];
  is_self: boolean;
}

export interface PostListResponse {
  cluster_key: ClusterKey;
  posts: PostRead[];
}

export interface FriendOverlayNode {
  id: string;
  display_name: string;
  cluster_key: ClusterKey;
  post_count: number;
}

export interface UserSearchResult {
  id: string;
  display_name: string;
  bio: string;
  avatar_url: string | null;
  follower_count: number;
  following_count: number;
  top_clusters: string[];
  relationship_following: boolean;
}

export interface UserProfile {
  id: string;
  display_name: string;
  bio: string;
  avatar_url: string | null;
  is_public: boolean;
  follower_count: number;
  following_count: number;
  created_at_public: boolean;
  serendipity_enabled: boolean;
  thought_count: number;
  cluster_count: number;
  top_clusters: string[];
  notification_prefs: Record<string, boolean>;
  onboarding_v2_completed: boolean;
  created_at: string | null;
}

export interface GraphNode {
  id: string;
  content: string;
  preview: string;
  created_at: string;
  emotion: string;
  topics: string[];
  cluster_id: string | null;
  cluster_label: string | null;
  color: string;
  size: number;
  connection_count: number;
  activity_score: number;
  author_id?: string | null;
  author_display_name?: string | null;
  visibility?: string | null;
  is_social?: boolean;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  kind: string;
  weight: number;
}

export interface GraphCluster {
  id: string;
  label: string;
  color: string;
  percentage: number;
  thought_count: number;
  trend: string;
  dominant_themes: string[];
  emotion_distribution: Record<string, number>;
}

export interface GraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
  clusters: GraphCluster[];
  mood: "neutral" | "focused" | "chaotic";
  first_thought_at: string | null;
  last_thought_at: string | null;
}

export interface TrendingCluster {
  label: string;
  growth_percentage: number;
  user_count: number;
  thought_count: number;
  sample_thoughts: string[];
}

export interface SnapshotRead {
  id: string;
  user_id: string;
  user_display_name: string;
  image_url: string;
  thumbnail_url: string | null;
  metadata: Record<string, unknown>;
  caption: string;
  is_public: boolean;
  created_at: string;
}

export interface WeeklyReport {
  id: string;
  user_id: string;
  user_display_name: string;
  week_start: string;
  week_end: string;
  content: Record<string, unknown>;
  image_url: string | null;
  seen: boolean;
  created_at: string;
}

export interface SerendipityMatch {
  id: string;
  alias: string;
  thought_preview: string;
  shared_topics: string[];
  similarity_score: number;
  created_at: string;
}

export interface SerendipityResponse {
  enabled: boolean;
  latest_thought_preview: string | null;
  matches: SerendipityMatch[];
}

export const thoughtApi = {
  requestMagicLink: (email: string) =>
    request<MagicLinkResponse>("/auth/request-link", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),
  verifyMagicToken: (token: string) =>
    request<SessionPayload>("/auth/verify", {
      method: "POST",
      body: JSON.stringify({ token }),
    }),
  logout: () => request<{ ok: boolean }>("/auth/logout", { method: "POST" }),
  getGraph: () => request<GraphResponse>("/graph"),
  createThought: (payload: { content: string; visibility?: "public" | "private" }) =>
    request<GraphNode>("/thoughts", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getMe: () => request<UserProfile>("/users/me"),
  updateDiscoverySettings: (serendipityEnabled: boolean) =>
    request<{ serendipity_enabled: boolean }>("/users/me/discovery", {
      method: "PATCH",
      body: JSON.stringify({ serendipity_enabled: serendipityEnabled }),
    }),
  getFriends: () => request<FriendsListResponse>("/friends/"),
  requestFriend: (userId: string) =>
    request<FriendSummary>("/friends/request", {
      method: "POST",
      body: JSON.stringify({ user_id: userId }),
    }),
  acceptFriend: (userId: string) =>
    request<FriendSummary>(`/friends/${encodeURIComponent(userId)}/accept`, { method: "POST" }),
  declineFriend: (userId: string) =>
    request<FriendSummary>(`/friends/${encodeURIComponent(userId)}/decline`, { method: "POST" }),
  searchUsers: (q: string) =>
    request<UserSearchResult[]>(`/users/search?q=${encodeURIComponent(q)}`),
  createPost: (payload: {
    cluster_key: ClusterKey;
    caption: string;
    media_url?: string | null;
    location?: string | null;
    visibility: PostVisibility;
  }) =>
    request<PostRead>("/posts/", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getClusterFeed: (cluster: ClusterKey) =>
    request<PostListResponse>(`/posts/cluster/${cluster}`),
  deletePost: (postId: string) =>
    request<{ deleted: boolean }>(`/posts/${postId}`, { method: "DELETE" }),
  getFriendsOverlay: () => request<{ nodes: FriendOverlayNode[] }>("/graph/friends-overlay"),
  getFriendSuggestions: () => request<FriendSummary[]>("/friends/suggestions"),
  reactToPost: (postId: string) =>
    request<ReactionToggleResponse>(`/posts/${encodeURIComponent(postId)}/react`, {
      method: "POST",
    }),
  getComments: (postId: string) =>
    request<{ post_id: string; comments: CommentRead[] }>(
      `/posts/${encodeURIComponent(postId)}/comments`,
    ),
  addComment: (postId: string, content: string) =>
    request<CommentRead>(`/posts/${encodeURIComponent(postId)}/comments`, {
      method: "POST",
      body: JSON.stringify({ content }),
    }),
  deleteComment: (commentId: string) =>
    request<{ deleted: boolean }>(`/posts/comments/${encodeURIComponent(commentId)}`, {
      method: "DELETE",
    }),
  getNotifications: () => request<NotificationItem[]>("/notifications"),
  markNotificationRead: (id: string, read: boolean) =>
    request<NotificationItem>(`/notifications/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify({ read }),
    }),
  getProfileSummary: (userId: string) =>
    request<ProfileSummary>(`/users/${encodeURIComponent(userId)}/summary`),
  getTrendingClusters: () => request<TrendingCluster[]>("/social/trending-clusters"),
  getSerendipity: () => request<SerendipityResponse>("/social/serendipity"),
  createSnapshot: (caption: string, isPublic: boolean) =>
    request<SnapshotRead>("/snapshots", {
      method: "POST",
      body: JSON.stringify({ caption, is_public: isPublic }),
    }),
  getSnapshots: () => request<SnapshotRead[]>("/snapshots"),
  getRecentPublicSnapshots: () => request<SnapshotRead[]>("/snapshots/recent/public"),
  generateWeeklyReport: () =>
    request<WeeklyReport>("/reports/generate", {
      method: "POST",
    }),
  getReports: () => request<WeeklyReport[]>("/reports"),
  getLatestReport: () => request<WeeklyReport>("/reports/latest"),
};
