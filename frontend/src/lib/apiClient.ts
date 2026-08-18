const API_URL = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";
const API_PREFIX = `${API_URL}/api`;
const TOKEN_KEY = "thoughtgraph:session";

function buildApiUrl(path: string) {
  if (!path) return path;
  if (/^https?:\/\//i.test(path)) return path;
  if (path.startsWith("/")) return `${API_URL}${path}`;
  return `${API_URL}/${path}`;
}

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
    ...(init?.headers as Record<string, string> | undefined),
  };
  const isJsonBody =
    init?.body !== undefined &&
    init?.body !== null &&
    !(init.body instanceof FormData) &&
    !(init.body instanceof Blob) &&
    !(init.body instanceof ArrayBuffer);
  if (isJsonBody && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  if (session?.session_token) {
    headers["Authorization"] = `Bearer ${session.session_token}`;
  }
  const response = await fetch(buildApiUrl(path.startsWith("/api/") ? path : `${API_PREFIX}${path}`), {
    ...init,
    headers,
  });
  if (!response.ok) {
    if (response.status === 401 && session) {
      clearSession();
      window.dispatchEvent(new Event("thoughtgraph:session-expired"));
    }
    const text = await response.text().catch(() => "");
    throw new Error(text || `request failed ${response.status}`);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function resolveMediaUrl(path: string | null | undefined) {
  if (!path) return null;
  const resolved = buildApiUrl(path);
  const session = loadSession();
  if (!session?.session_token) {
    return resolved;
  }
  const separator = resolved.includes("?") ? "&" : "?";
  return `${resolved}${separator}session_token=${encodeURIComponent(session.session_token)}`;
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

export interface SocialRelationshipRead {
  target_user_id?: string;
  following: boolean;
  followed_by: boolean;
  friendship_state: "none" | "incoming" | "outgoing" | "accepted" | "declined" | "suggested";
  blocked: boolean;
  muted: boolean;
  restricted: boolean;
  blocked_by_target: boolean;
  restricted_by_target: boolean;
}

export interface SocialProfileRead {
  id: string;
  display_name: string;
  bio: string;
  is_public: boolean;
  node_count: number;
  cluster_count: number;
  top_clusters: string[];
  created_at: string | null;
  relationship: SocialRelationshipRead;
}

export interface SocialSearchResult {
  id: string;
  display_name: string;
  bio: string;
  is_public: boolean;
  top_clusters: string[];
  relationship: SocialRelationshipRead;
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

/**
 * Legacy v1 social/feed client retained for older, currently inactive screens.
 * GraphShell and new frontend work should use graphApi below.
 */
export const legacyThoughtApi = {
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
};

export interface GraphViewport {
  center_x: number;
  center_y: number;
  zoom_hint: number;
}

export interface GraphNodeRecord {
  id: string;
  kind: "thought" | "image" | "video" | "link" | string;
  title: string | null;
  content_text: string | null;
  preview_text: string | null;
  visibility: "private" | "public" | string;
  created_at: string;
  updated_at: string;
  topics: string[];
  cluster_id: string | null;
  cluster_label: string | null;
  cluster_color: string | null;
  connection_count: number;
  x: number;
  y: number;
  media_url: string | null;
  link_url: string | null;
  author_id: string | null;
  author_display_name: string | null;
  relationship_to_viewer: string | null;
  is_social: boolean;
  media_asset_id: string | null;
  media_kind: string | null;
  media_status: string | null;
  thumbnail_url: string | null;
  playback_url: string | null;
  duration_seconds: number | null;
  reply_to_node_id: string | null;
  quote_of_node_id: string | null;
}

export interface GraphEdgeRecord {
  id: string;
  source: string;
  target: string;
  edge_type: string;
  weight: number;
  explanation: Record<string, unknown>;
}

export interface GraphClusterRecord {
  id: string;
  label: string;
  color: string;
  summary: string | null;
  node_count: number;
  dominant_topics: string[];
  centroid_x: number;
  centroid_y: number;
  owner_user_id: string | null;
  is_social: boolean;
}

export interface GraphExplanationRecord {
  reason: string;
  generated_at: string;
}

export interface GraphNativeResponse {
  nodes: GraphNodeRecord[];
  edges: GraphEdgeRecord[];
  clusters: GraphClusterRecord[];
  viewport: GraphViewport;
  explanation: GraphExplanationRecord;
  social_mode: boolean;
}

export interface GraphSearchResult {
  node_id: string;
  title: string | null;
  preview_text: string | null;
  cluster_label: string | null;
  cluster_color: string | null;
  score: number;
}

export interface NodeCreateRequest {
  kind: "thought" | "image" | "video" | "link";
  title?: string;
  content_text?: string;
  visibility: "private" | "friends" | "public";
  link_url?: string;
  media?: {
    asset_id?: string;
    url?: string;
    filename?: string;
    mime_type?: string;
    size_bytes?: number;
    width?: number;
    height?: number;
  };
  reply_to_node_id?: string | null;
  quote_of_node_id?: string | null;
}

export interface NodeRead extends GraphNodeRecord {
  metadata_json: Record<string, unknown>;
}

export interface NodeThreadResponse {
  root: NodeRead;
  replies: NodeRead[];
  quoted_node: NodeRead | null;
}

export interface NodeListResponse {
  items: NodeRead[];
}

export interface MeRead {
  id: string;
  display_name: string;
  bio: string;
  is_public: boolean;
  onboarding_v2_completed: boolean;
  created_at: string | null;
  node_count: number;
  cluster_count: number;
  top_clusters: string[];
  follower_count: number;
  following_count: number;
}

export interface FriendListItem {
  id: string;
  display_name: string;
  bio: string;
  top_clusters: string[];
  friendship_state: string;
  relationship: SocialRelationshipRead;
  updated_at: string;
}

export interface FriendsResponse {
  friends: FriendListItem[];
  incoming: FriendListItem[];
  outgoing: FriendListItem[];
}

export interface SocialNeighborhoodItem {
  user_id: string;
  display_name: string;
  relationship: SocialRelationshipRead;
  shared_cluster_labels: string[];
  shared_topics: string[];
  visible_node_count: number;
}

export interface SocialNeighborhoodResponse {
  items: SocialNeighborhoodItem[];
}

export interface DiscoveryScoreBreakdown {
  relevance: number;
  novelty: number;
  trust: number;
  diversity: number;
  social_proximity: number;
  total: number;
}

export interface DiscoveryExplanation {
  primary_reason: string;
  summary: string;
  matched_topics: string[];
  relationship_to_viewer: string | null;
  signal_notes: string[];
  unavailable_filters: string[];
  score_breakdown: DiscoveryScoreBreakdown;
}

export interface DiscoveryNodeItem {
  node: GraphNodeRecord;
  explanation: DiscoveryExplanation;
}

export interface DiscoveryPersonItem {
  user_id: string;
  display_name: string;
  bio: string;
  shared_topics: string[];
  shared_cluster_labels: string[];
  visible_node_count: number;
  relationship: SocialRelationshipRead;
  explanation: DiscoveryExplanation;
}

export interface DiscoveryFilterAvailability {
  close_to_me: boolean;
  outside_my_bubble: boolean;
  high_evidence: boolean;
  new_low_spread: boolean;
  trusted_only: boolean;
}

export interface DiscoveryExploreFilters {
  q?: string;
  close_to_me?: boolean;
  outside_my_bubble?: boolean;
  high_evidence?: boolean;
  new_low_spread?: boolean;
  trusted_only?: boolean;
  limit?: number;
}

export interface DiscoveryExploreResponse {
  materialization_id: string;
  generated_at: string;
  filters: {
    q: string | null;
    close_to_me: boolean;
    outside_my_bubble: boolean;
    high_evidence: boolean;
    new_low_spread: boolean;
    trusted_only: boolean;
    limit: number;
  };
  filter_availability: DiscoveryFilterAvailability;
  explanation_summary: string;
  items: DiscoveryNodeItem[];
}

export interface RelatedIdeasResponse {
  materialization_id: string;
  generated_at: string;
  subject: GraphNodeRecord;
  explanation_summary: string;
  items: DiscoveryNodeItem[];
}

export interface AdjacentPeopleResponse {
  materialization_id: string;
  generated_at: string;
  explanation_summary: string;
  items: DiscoveryPersonItem[];
}

export interface RestrictionUpdate {
  kind: "blocked" | "muted" | "restricted";
  active: boolean;
}

export interface MeUpdateRequest {
  display_name?: string;
  bio?: string;
  is_public?: boolean;
  onboarding_v2_completed?: boolean;
}

export interface MediaRenditionRead {
  label: string;
  mime_type: string | null;
  width: number | null;
  height: number | null;
  duration_seconds: number | null;
  url: string;
  size_bytes: number | null;
}

export interface MediaAssetRead {
  id: string;
  kind: "image" | "video" | string;
  source_kind: string;
  filename: string | null;
  mime_type: string | null;
  size_bytes: number | null;
  width: number | null;
  height: number | null;
  duration_seconds: number | null;
  status: "awaiting_upload" | "uploaded" | "processing" | "ready" | "failed" | string;
  moderation_status: string;
  original_url: string | null;
  playback_url: string | null;
  thumbnail_url: string | null;
  renditions: MediaRenditionRead[];
  error_message: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface MediaUploadTarget {
  method: "PUT" | string;
  upload_url: string;
  expires_at: string;
  headers: Record<string, string>;
}

export interface MediaUploadCreateResponse {
  asset: MediaAssetRead;
  upload: MediaUploadTarget;
}

export interface MediaUploadRequest {
  kind: "image" | "video";
  filename: string;
  mime_type: string;
  size_bytes: number;
}

export interface UploadProgress {
  loaded: number;
  total: number;
  percent: number;
}

export interface ReflectiveEvidenceRead {
  evidence_type: "node" | "cluster" | "edge" | "event" | "source";
  id: string;
  label: string;
  reason: string;
  created_at: string | null;
  metadata: Record<string, unknown>;
}

export interface ReflectiveMetricRead {
  key: string;
  label: string;
  current: number;
  previous: number;
  delta: number;
  unit: string;
  method: string;
}

export interface ReflectiveConfidenceRead {
  score: number;
  label: "low" | "medium" | "high";
  basis: string;
  sample_size: number;
  minimum_sample_size: number;
}

export type ReflectiveCorrection = "inaccurate" | "wrong_evidence" | "not_useful";

export interface ReflectiveFeedbackRead {
  dismissed: boolean;
  correction: ReflectiveCorrection | null;
  annotation: string | null;
  updated_at: string | null;
}

export interface PersistedReflectiveInsightRead {
  id: string;
  kind: "attention_drift" | "source_shaping_summary";
  contract_version: number;
  title: string;
  summary: string;
  generated_at: string;
  status: "ready" | "insufficient_data";
  window: {
    current_start: string;
    current_end: string;
    comparison_start: string;
    comparison_end: string;
  };
  metrics: ReflectiveMetricRead[];
  evidence: ReflectiveEvidenceRead[];
  confidence: ReflectiveConfidenceRead;
  limitations: string[];
  action_hint: string | null;
  feedback: ReflectiveFeedbackRead;
}

export interface ReflectiveLoopRunRead {
  user_id: string;
  generated_at: string;
  workflow_job_id: string | null;
  workflow_status: string | null;
  persisted_insight_ids: string[];
}

export interface ReflectiveFeedbackUpdate {
  dismissed?: boolean;
  correction?: ReflectiveCorrection | null;
  annotation?: string | null;
}

function withQuery(path: string, params: Record<string, string | number | boolean | null | undefined>) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") return;
    search.set(key, String(value));
  });
  const query = search.toString();
  return query ? `${path}?${query}` : path;
}

async function uploadBinary(
  path: string,
  method: string,
  file: File,
  headers: Record<string, string>,
  onProgress?: (progress: UploadProgress) => void,
) {
  const session = loadSession();
  return await new Promise<MediaAssetRead>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open(method || "PUT", buildApiUrl(path), true);
    Object.entries(headers).forEach(([key, value]) => xhr.setRequestHeader(key, value));
    if (session?.session_token) {
      xhr.setRequestHeader("Authorization", `Bearer ${session.session_token}`);
    }
    if (file.type) {
      xhr.setRequestHeader("Content-Type", file.type);
    }
    xhr.setRequestHeader("X-Upload-Filename", file.name);
    xhr.upload.onprogress = (event) => {
      if (!onProgress || !event.lengthComputable) return;
      onProgress({
        loaded: event.loaded,
        total: event.total,
        percent: Math.round((event.loaded / event.total) * 100),
      });
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText) as MediaAssetRead);
        } catch {
          reject(new Error("upload completed but response could not be read"));
        }
        return;
      }
      if (xhr.status === 401 && session) {
        clearSession();
        window.dispatchEvent(new Event("thoughtgraph:session-expired"));
      }
      reject(new Error(xhr.responseText || `upload failed ${xhr.status}`));
    };
    xhr.onerror = () => reject(new Error("upload failed"));
    xhr.send(file);
  });
}

export const graphApi = {
  getGraph: (social = false) => request<GraphNativeResponse>(`/graph${social ? "?social=true" : ""}`),
  searchGraph: (q: string) => request<{ items: GraphSearchResult[] }>(`/graph/search?q=${encodeURIComponent(q)}`),
  createNode: (payload: NodeCreateRequest) =>
    request<NodeRead>("/nodes", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  listNodes: () => request<NodeListResponse>("/nodes"),
  getNode: (nodeId: string) => request<NodeRead>(`/nodes/${encodeURIComponent(nodeId)}`),
  getNodeThread: (nodeId: string) => request<NodeThreadResponse>(`/nodes/${encodeURIComponent(nodeId)}/thread`),
  getMe: () => request<MeRead>("/users/me"),
  updateMe: (payload: MeUpdateRequest) =>
    request<MeRead>("/users/me", {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  searchUsers: (q: string) =>
    request<SocialSearchResult[]>(`/users/search?q=${encodeURIComponent(q)}`),
  getUserProfile: (userId: string) => request<SocialProfileRead>(`/users/${encodeURIComponent(userId)}`),
  followUser: (userId: string) =>
    request<SocialRelationshipRead>(`/social/follow/${encodeURIComponent(userId)}`, {
      method: "POST",
    }),
  unfollowUser: (userId: string) =>
    request<SocialRelationshipRead>(`/social/follow/${encodeURIComponent(userId)}`, {
      method: "DELETE",
    }),
  getRelationship: (userId: string) =>
    request<SocialRelationshipRead>(`/social/relationship/${encodeURIComponent(userId)}`),
  updateRestriction: (userId: string, payload: RestrictionUpdate) =>
    request<SocialRelationshipRead>(`/social/restrictions/${encodeURIComponent(userId)}`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getNeighborhood: () => request<SocialNeighborhoodResponse>("/social/neighborhood"),
  getDiscoveryExplore: (filters: DiscoveryExploreFilters = {}) =>
    request<DiscoveryExploreResponse>(
      withQuery("/discovery/explore", {
        q: filters.q?.trim() || undefined,
        close_to_me: filters.close_to_me,
        outside_my_bubble: filters.outside_my_bubble,
        high_evidence: filters.high_evidence,
        new_low_spread: filters.new_low_spread,
        trusted_only: filters.trusted_only,
        limit: filters.limit,
      }),
    ),
  getRelatedIdeas: (nodeId: string, limit?: number) =>
    request<RelatedIdeasResponse>(
      withQuery(`/discovery/related/${encodeURIComponent(nodeId)}`, { limit }),
    ),
  getAdjacentPeople: (limit?: number) =>
    request<AdjacentPeopleResponse>(withQuery("/discovery/people-adjacent", { limit })),
  getFriends: () => request<FriendsResponse>("/friends"),
  requestFriend: (userId: string) =>
    request<SocialRelationshipRead>("/friends/request", {
      method: "POST",
      body: JSON.stringify({ user_id: userId }),
    }),
  acceptFriend: (userId: string) =>
    request<SocialRelationshipRead>(`/friends/${encodeURIComponent(userId)}/accept`, {
      method: "POST",
    }),
  declineFriend: (userId: string) =>
    request<SocialRelationshipRead>(`/friends/${encodeURIComponent(userId)}/decline`, {
      method: "POST",
    }),
  removeFriend: (userId: string) =>
    request<SocialRelationshipRead>(`/friends/${encodeURIComponent(userId)}`, {
      method: "DELETE",
    }),
  logout: () => request<{ ok: boolean }>("/auth/logout", { method: "POST" }),
  enterAsGuest: (signal?: AbortSignal) =>
    request<SessionPayload>("/auth/guest", { method: "POST", signal }),
  requestLink: (email: string) =>
    request<MagicLinkResponse>("/auth/request-link", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),
  verifyLink: (token: string) =>
    request<SessionPayload>("/auth/verify", {
      method: "POST",
      body: JSON.stringify({ token }),
    }),
  createMediaUpload: (payload: MediaUploadRequest) =>
    request<MediaUploadCreateResponse>("/media/uploads", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  uploadMediaContent: (
    upload: MediaUploadTarget,
    file: File,
    onProgress?: (progress: UploadProgress) => void,
  ) => uploadBinary(upload.upload_url, upload.method, file, upload.headers, onProgress),
  getMediaAsset: (assetId: string) =>
    request<MediaAssetRead>(`/media/assets/${encodeURIComponent(assetId)}`),
  retryMediaAsset: (assetId: string) =>
    request<MediaAssetRead>(`/media/assets/${encodeURIComponent(assetId)}/retry`, {
      method: "POST",
    }),
  getReflectiveInsights: (includeDismissed = false) =>
    request<PersistedReflectiveInsightRead[]>(
      `/reflective-insights${includeDismissed ? "?include_dismissed=true" : ""}`,
    ),
  runReflectiveInsights: () =>
    request<ReflectiveLoopRunRead>("/reflective-insights/run", {
      method: "POST",
      body: JSON.stringify({ run_inline: true }),
    }),
  updateReflectiveInsightFeedback: (insightId: string, payload: ReflectiveFeedbackUpdate) =>
    request<PersistedReflectiveInsightRead>(`/reflective-insights/${encodeURIComponent(insightId)}/feedback`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
};

/** @deprecated Use legacyThoughtApi only for quarantined legacy screens. */
export const thoughtApi = legacyThoughtApi;
