import type {
  GraphResponse,
  InfluenceScore,
  Insight,
  NotificationPreferencesResponse,
  NotificationItem,
  OnboardingState,
  ReplyThread,
  Snapshot,
  SocialFeedItem,
  ThoughtInput,
  TrendingCluster,
  UserProfile,
  UserSearchResult,
  WeeklyReport,
  SuggestedUser,
} from "../types";

const API_URL = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";
const API_PREFIX = `${API_URL}/api`;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_PREFIX}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed with ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export function getWebSocketUrl() {
  const url = new URL(API_URL);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname = "/api/ws";
  return url.toString();
}

export const api = {
  getGraph: (social = false) => request<GraphResponse>(`/graph${social ? "?social=true" : ""}`),
  getInsights: () => request<Insight[]>("/insights"),
  createThought: (payload: ThoughtInput) =>
    request("/thoughts", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  dismissInsight: (id: string) =>
    request<Insight>(`/insights/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ dismissed: true }),
    }),
  markInsightSeen: (id: string) =>
    request<Insight>(`/insights/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ seen: true }),
    }),
  seedDemo: () =>
    request<{ created: number }>("/demo/seed", {
      method: "POST",
    }),
  seedSocialDemo: () =>
    request<{ users_created: number; thoughts_created: number }>("/social/demo/seed", {
      method: "POST",
    }),
  getMe: () => request<UserProfile>("/users/me"),
  getUserProfile: (id: string) => request<UserProfile>(`/users/${id}`),
  searchUsers: (q = "") => request<UserSearchResult[]>(`/users/search?q=${encodeURIComponent(q)}`),
  followUser: (id: string) =>
    request<{ following: boolean }>(`/social/follow/${id}`, {
      method: "POST",
    }),
  unfollowUser: (id: string) =>
    request<{ following: boolean }>(`/social/follow/${id}`, {
      method: "DELETE",
    }),
  getNotifications: () => request<NotificationItem[]>("/notifications"),
  markNotificationRead: (id: string, read = true) =>
    request<NotificationItem>(`/notifications/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ read }),
    }),
  getReplyThread: (thoughtId: string) => request<ReplyThread>(`/social/replies/${thoughtId}`),
  getSocialFeed: () => request<SocialFeedItem[]>("/social/feed"),
  getInfluence: () => request<InfluenceScore[]>("/social/influence"),
  getInfluenceForUser: (userId: string) => request<InfluenceScore>(`/social/influence/${userId}`),
  getTrendingClusters: () => request<TrendingCluster[]>("/social/trending-clusters"),
  getSuggestedUsers: () => request<SuggestedUser[]>("/social/suggested-users"),
  createSnapshot: (caption: string, isPublic: boolean) =>
    request<Snapshot>("/snapshots", {
      method: "POST",
      body: JSON.stringify({ caption, is_public: isPublic }),
    }),
  getSnapshots: () => request<Snapshot[]>("/snapshots"),
  getRecentPublicSnapshots: () => request<Snapshot[]>("/snapshots/recent/public"),
  getSnapshot: (id: string) => request<Snapshot>(`/snapshots/${id}`),
  getPublicSnapshot: (id: string) => request<Snapshot>(`/snapshots/public/${id}`),
  deleteSnapshot: (id: string) =>
    request<{ deleted: boolean }>(`/snapshots/${id}`, {
      method: "DELETE",
    }),
  generateWeeklyReport: () =>
    request<WeeklyReport>("/reports/generate", {
      method: "POST",
    }),
  getReports: () => request<WeeklyReport[]>("/reports"),
  getLatestReport: () => request<WeeklyReport>("/reports/latest"),
  getReport: (id: string) => request<WeeklyReport>(`/reports/${id}`),
  updateNotificationPreferences: (payload: Record<string, boolean>) =>
    request<NotificationPreferencesResponse>("/users/me/notification-preferences", {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  updateOnboarding: (completed: boolean) =>
    request<OnboardingState>("/users/me/onboarding", {
      method: "PATCH",
      body: JSON.stringify({ completed }),
    }),
  updateThoughtVisibility: (visibility: "public" | "private") =>
    request<{ updated: number; visibility: string }>("/users/me/thought-visibility", {
      method: "PATCH",
      body: JSON.stringify({ visibility }),
    }),
  exportData: () => request<Record<string, unknown>>("/users/me/export"),
  deleteMe: () =>
    request<{ deleted: boolean }>("/users/me", {
      method: "DELETE",
    }),
};
