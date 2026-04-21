import { useCallback, useEffect, useMemo, useState } from "react";

import { api } from "../api/client";
import type {
  InfluenceScore,
  NotificationItem,
  ReplyThread,
  Snapshot,
  SocialFeedItem,
  SuggestedUser,
  TrendingCluster,
  UserProfile,
  UserSearchResult,
  WeeklyReport,
} from "../types";

interface SocialLayerState {
  me: UserProfile | null;
  users: UserSearchResult[];
  notifications: NotificationItem[];
  suggestedUsers: SuggestedUser[];
  trendingClusters: TrendingCluster[];
  feed: SocialFeedItem[];
  influence: InfluenceScore[];
  snapshots: Snapshot[];
  recentPublicSnapshots: Snapshot[];
  reports: WeeklyReport[];
  latestReport: WeeklyReport | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  seedNetwork: () => Promise<void>;
  toggleFollow: (userId: string, following: boolean) => Promise<void>;
  markNotificationRead: (notificationId: string) => Promise<void>;
  createSnapshot: (caption: string, isPublic: boolean) => Promise<Snapshot>;
  generateWeeklyReport: () => Promise<WeeklyReport>;
  updateNotificationPrefs: (payload: Record<string, boolean>) => Promise<void>;
  updateOnboarding: (completed: boolean) => Promise<void>;
  updateThoughtVisibility: (visibility: "public" | "private") => Promise<void>;
  exportData: () => Promise<Record<string, unknown>>;
  getReplyThread: (thoughtId: string) => Promise<ReplyThread>;
  getInfluenceForUser: (userId: string) => Promise<InfluenceScore>;
  getProfile: (userId: string) => Promise<UserProfile>;
  getPublicSnapshot: (snapshotId: string) => Promise<Snapshot>;
}

export function useSocialLayer(): SocialLayerState {
  const [me, setMe] = useState<UserProfile | null>(null);
  const [users, setUsers] = useState<UserSearchResult[]>([]);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [suggestedUsers, setSuggestedUsers] = useState<SuggestedUser[]>([]);
  const [trendingClusters, setTrendingClusters] = useState<TrendingCluster[]>([]);
  const [feed, setFeed] = useState<SocialFeedItem[]>([]);
  const [influence, setInfluence] = useState<InfluenceScore[]>([]);
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [recentPublicSnapshots, setRecentPublicSnapshots] = useState<Snapshot[]>([]);
  const [reports, setReports] = useState<WeeklyReport[]>([]);
  const [latestReport, setLatestReport] = useState<WeeklyReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setError(null);
      const [
        profile,
        searchResults,
        notificationList,
        nextSuggested,
        nextTrending,
        nextFeed,
        nextInfluence,
        nextSnapshots,
        nextRecentSnapshots,
        nextReports,
      ] = await Promise.all([
        api.getMe(),
        api.searchUsers(""),
        api.getNotifications(),
        api.getSuggestedUsers(),
        api.getTrendingClusters(),
        api.getSocialFeed(),
        api.getInfluence(),
        api.getSnapshots(),
        api.getRecentPublicSnapshots(),
        api.getReports(),
      ]);
      setMe(profile);
      setUsers(searchResults);
      setNotifications(notificationList);
      setSuggestedUsers(nextSuggested);
      setTrendingClusters(nextTrending);
      setFeed(nextFeed);
      setInfluence(nextInfluence);
      setSnapshots(nextSnapshots);
      setRecentPublicSnapshots(nextRecentSnapshots);
      setReports(nextReports);
      setLatestReport(nextReports[0] ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load social layer.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const actions = useMemo(
    () => ({
      async seedNetwork() {
        await api.seedSocialDemo();
        await refresh();
      },
      async toggleFollow(userId: string, following: boolean) {
        if (following) {
          await api.unfollowUser(userId);
        } else {
          await api.followUser(userId);
        }
        await refresh();
      },
      async markNotificationRead(notificationId: string) {
        const updated = await api.markNotificationRead(notificationId, true);
        setNotifications((current) => current.map((item) => (item.id === notificationId ? updated : item)));
      },
      async createSnapshot(caption: string, isPublic: boolean) {
        const snapshot = await api.createSnapshot(caption, isPublic);
        await refresh();
        return snapshot;
      },
      async generateWeeklyReport() {
        const report = await api.generateWeeklyReport();
        await refresh();
        return report;
      },
      async updateNotificationPrefs(payload: Record<string, boolean>) {
        await api.updateNotificationPreferences(payload);
        await refresh();
      },
      async updateOnboarding(completed: boolean) {
        await api.updateOnboarding(completed);
        await refresh();
      },
      async updateThoughtVisibility(visibility: "public" | "private") {
        await api.updateThoughtVisibility(visibility);
        await refresh();
      },
      async exportData() {
        return api.exportData();
      },
      async getReplyThread(thoughtId: string) {
        return api.getReplyThread(thoughtId);
      },
      async getInfluenceForUser(userId: string) {
        return api.getInfluenceForUser(userId);
      },
      async getProfile(userId: string) {
        return api.getUserProfile(userId);
      },
      async getPublicSnapshot(snapshotId: string) {
        return api.getPublicSnapshot(snapshotId);
      },
    }),
    [refresh],
  );

  return {
    me,
    users,
    notifications,
    suggestedUsers,
    trendingClusters,
    feed,
    influence,
    snapshots,
    recentPublicSnapshots,
    reports,
    latestReport,
    loading,
    error,
    refresh,
    ...actions,
  };
}
