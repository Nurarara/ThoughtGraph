export type Mood = "neutral" | "focused" | "chaotic";

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
  mood: Mood;
  first_thought_at: string | null;
  last_thought_at: string | null;
  social_enabled?: boolean;
  social_nodes?: GraphNode[];
  social_edges?: GraphEdge[];
  social_profiles?: GraphAuthor[];
}

export interface GraphAuthor {
  user_id: string;
  display_name: string;
  avatar_url: string | null;
  color: string;
}

export interface Insight {
  id: string;
  kind: string;
  content: string;
  raw_content: string;
  supporting_data: Record<string, unknown>;
  seen: boolean;
  dismissed: boolean;
  created_at: string;
}

export interface ThoughtInput {
  content: string;
  visibility?: "public" | "private";
  reply_to_id?: string | null;
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
  thought_count: number;
  cluster_count: number;
  top_clusters: string[];
  notification_prefs: Record<string, boolean>;
  onboarding_v2_completed: boolean;
  created_at?: string | null;
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

export interface ReplyThread {
  root: SocialThought;
  replies: SocialThought[];
}

export interface SocialThought {
  id: string;
  content: string;
  created_at: string;
  emotion: string;
  topics: string[];
  author_id: string;
  author_display_name: string;
  visibility: string;
  reply_to_id: string | null;
  reply_to_user_id: string | null;
}

export interface InfluenceScore {
  user_id: string;
  target_user_id: string;
  target_display_name: string;
  score: number;
  edge_count: number;
  cluster_overlap: number;
  reply_count: number;
  summary: string;
  computed_at: string;
}

export interface TrendingCluster {
  label: string;
  growth_percentage: number;
  user_count: number;
  thought_count: number;
  sample_thoughts: string[];
}

export interface SocialFeedItem {
  thought: SocialThought;
  relationship: string;
}

export interface Snapshot {
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

export interface NotificationPreferencesResponse {
  notification_prefs: Record<string, boolean>;
}

export interface SuggestedUser {
  user_id: string;
  display_name: string;
  avatar_url: string | null;
  top_clusters: string[];
  followed_at: string;
}

export interface OnboardingState {
  completed: boolean;
}
