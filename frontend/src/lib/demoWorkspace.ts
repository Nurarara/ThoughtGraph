import type {
  DiscoveryExploreResponse,
  GraphNativeResponse,
  GraphNodeRecord,
  GraphSearchResult,
  MeRead,
  NodeCreateRequest,
  NodeRead,
  NodeThreadResponse,
  SessionPayload,
} from "./apiClient";

const GRAPH_STORAGE_KEY = "thoughtgraph:demo-graph:v1";
const PROFILE_STORAGE_KEY = "thoughtgraph:demo-profile:v1";
const DEMO_USER_ID = "demo-explorer";
const DEMO_TIMESTAMP = "2026-08-18T09:00:00.000Z";

export const DEMO_SESSION: SessionPayload = {
  session_token: "thoughtgraph-local-demo-v1",
  user_id: DEMO_USER_ID,
  display_name: "Guest Explorer",
  email: "",
  is_new_user: false,
};

const clusters = [
  {
    id: "demo-cluster-systems",
    label: "Ideas & Systems",
    color: "#f4ae42",
    summary: "How tools, structures, and ideas shape one another.",
    node_count: 3,
    dominant_topics: ["systems", "design", "thinking"],
    centroid_x: -170,
    centroid_y: -90,
    owner_user_id: DEMO_USER_ID,
    is_social: false,
  },
  {
    id: "demo-cluster-making",
    label: "Work & Making",
    color: "#3fc6dc",
    summary: "Experiments that turn reflection into something tangible.",
    node_count: 3,
    dominant_topics: ["craft", "product", "learning"],
    centroid_x: 210,
    centroid_y: -45,
    owner_user_id: DEMO_USER_ID,
    is_social: false,
  },
  {
    id: "demo-cluster-practice",
    label: "Life & Practice",
    color: "#7de3c3",
    summary: "Small practices that support attention and intentional living.",
    node_count: 3,
    dominant_topics: ["attention", "health", "practice"],
    centroid_x: 0,
    centroid_y: 205,
    owner_user_id: DEMO_USER_ID,
    is_social: false,
  },
];

function demoNode(
  id: string,
  title: string,
  content: string,
  topics: string[],
  clusterIndex: number,
  x: number,
  y: number,
  connectionCount: number,
  kind: "thought" | "link" = "thought",
  linkUrl: string | null = null,
): GraphNodeRecord {
  const cluster = clusters[clusterIndex];
  return {
    id,
    kind,
    title,
    content_text: content,
    preview_text: content.slice(0, 180),
    visibility: "private",
    created_at: DEMO_TIMESTAMP,
    updated_at: DEMO_TIMESTAMP,
    topics,
    cluster_id: cluster.id,
    cluster_label: cluster.label,
    cluster_color: cluster.color,
    connection_count: connectionCount,
    x,
    y,
    media_url: null,
    link_url: linkUrl,
    author_id: DEMO_USER_ID,
    author_display_name: "Guest Explorer",
    relationship_to_viewer: "self",
    is_social: false,
    media_asset_id: null,
    media_kind: null,
    media_status: null,
    thumbnail_url: null,
    playback_url: null,
    duration_seconds: null,
    reply_to_node_id: null,
    quote_of_node_id: null,
  };
}

const initialGraph: GraphNativeResponse = {
  nodes: [
    demoNode("demo-node-1", "Tools should reveal structure", "The best thinking tools help relationships become visible without pretending to know more than the evidence supports.", ["systems", "tools", "evidence"], 0, -250, -125, 3),
    demoNode("demo-node-2", "Meaning needs spatial context", "A thought feels different when it is seen beside the ideas that attracted it and the questions it still leaves open.", ["meaning", "space", "context"], 0, -105, -25, 3),
    demoNode("demo-node-3", "Restraint creates legibility", "Progressive disclosure can make a complex knowledge system feel calm instead of empty or overwhelming.", ["design", "restraint", "clarity"], 0, -235, 75, 2),
    demoNode("demo-node-4", "Build the smallest honest loop", "Capture, connect, inspect the evidence, and only then add another layer of intelligence.", ["product", "craft", "iteration"], 1, 145, -145, 3),
    demoNode("demo-node-5", "Prototype with real boundaries", "A prototype becomes trustworthy when its limitations are visible and its derived views can be rebuilt.", ["prototype", "trust", "architecture"], 1, 295, -45, 3),
    demoNode("demo-node-6", "Questions are product material", "The questions users repeat are often better roadmap evidence than a long feature wishlist.", ["learning", "product", "questions"], 1, 185, 80, 2),
    demoNode("demo-node-7", "Attention follows environment", "Changing the shape of a workspace can change which ideas are easy to return to and which quietly disappear.", ["attention", "environment", "practice"], 2, -100, 185, 3),
    demoNode("demo-node-8", "Small rituals compound", "A short daily capture habit can create enough history for reflection without turning life into measurement.", ["practice", "reflection", "habit"], 2, 55, 265, 3),
    demoNode("demo-node-9", "Leave room for uncertainty", "Reflection should invite a closer look, not turn incomplete personal data into certainty.", ["uncertainty", "evidence", "reflection"], 2, 120, 155, 2, "link", "https://example.com/reflection"),
  ],
  edges: [
    { id: "demo-edge-1", source: "demo-node-1", target: "demo-node-2", edge_type: "semantic", weight: 0.86, explanation: { reason: "shared systems context" } },
    { id: "demo-edge-2", source: "demo-node-1", target: "demo-node-4", edge_type: "semantic", weight: 0.72, explanation: { reason: "tool-making connection" } },
    { id: "demo-edge-3", source: "demo-node-1", target: "demo-node-5", edge_type: "semantic", weight: 0.77, explanation: { reason: "trustworthy systems" } },
    { id: "demo-edge-4", source: "demo-node-2", target: "demo-node-3", edge_type: "semantic", weight: 0.74, explanation: { reason: "spatial legibility" } },
    { id: "demo-edge-5", source: "demo-node-2", target: "demo-node-7", edge_type: "semantic", weight: 0.68, explanation: { reason: "environment shapes attention" } },
    { id: "demo-edge-6", source: "demo-node-4", target: "demo-node-5", edge_type: "semantic", weight: 0.89, explanation: { reason: "prototype discipline" } },
    { id: "demo-edge-7", source: "demo-node-4", target: "demo-node-6", edge_type: "semantic", weight: 0.75, explanation: { reason: "learning loop" } },
    { id: "demo-edge-8", source: "demo-node-6", target: "demo-node-8", edge_type: "semantic", weight: 0.64, explanation: { reason: "questions become practice" } },
    { id: "demo-edge-9", source: "demo-node-7", target: "demo-node-8", edge_type: "semantic", weight: 0.84, explanation: { reason: "attention practice" } },
    { id: "demo-edge-10", source: "demo-node-8", target: "demo-node-9", edge_type: "semantic", weight: 0.79, explanation: { reason: "honest reflection" } },
  ],
  clusters,
  viewport: { center_x: 0, center_y: 35, zoom_hint: 1 },
  explanation: { reason: "Browser-local interactive demonstration", generated_at: DEMO_TIMESTAMP },
  social_mode: false,
};

const initialProfile: MeRead = {
  id: DEMO_USER_ID,
  display_name: "Guest Explorer",
  bio: "Exploring a private browser-local ThoughtGraph.",
  is_public: false,
  onboarding_v2_completed: true,
  created_at: DEMO_TIMESTAMP,
  node_count: initialGraph.nodes.length,
  cluster_count: initialGraph.clusters.length,
  top_clusters: initialGraph.clusters.map((cluster) => cluster.label),
  follower_count: 0,
  following_count: 0,
};

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

export function isDemoSession(session: SessionPayload | null): boolean {
  return Boolean(
    session && (session.session_token === DEMO_SESSION.session_token || session.user_id.startsWith("guest-")),
  );
}

export function loadDemoGraph(): GraphNativeResponse {
  try {
    const stored = localStorage.getItem(GRAPH_STORAGE_KEY);
    if (!stored) return clone(initialGraph);
    const parsed = JSON.parse(stored) as GraphNativeResponse;
    return Array.isArray(parsed.nodes) && Array.isArray(parsed.edges) && Array.isArray(parsed.clusters)
      ? parsed
      : clone(initialGraph);
  } catch {
    return clone(initialGraph);
  }
}

export function saveDemoGraph(graph: GraphNativeResponse): void {
  localStorage.setItem(GRAPH_STORAGE_KEY, JSON.stringify(graph));
}

export function loadDemoProfile(): MeRead {
  try {
    const stored = localStorage.getItem(PROFILE_STORAGE_KEY);
    return stored ? { ...clone(initialProfile), ...(JSON.parse(stored) as Partial<MeRead>) } : clone(initialProfile);
  } catch {
    return clone(initialProfile);
  }
}

export function saveDemoProfile(profile: MeRead): void {
  localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(profile));
}

function topicsFrom(payload: NodeCreateRequest): string[] {
  const source = `${payload.title ?? ""} ${payload.content_text ?? ""}`.toLowerCase();
  const ignored = new Set(["about", "after", "again", "from", "have", "into", "that", "their", "this", "with", "your"]);
  return [...new Set(source.match(/[a-z]{4,}/g) ?? [])].filter((word) => !ignored.has(word)).slice(0, 4);
}

function safeHttpUrl(value: string | undefined): string | null {
  if (!value) return null;
  try {
    const parsed = new URL(value);
    return parsed.protocol === "http:" || parsed.protocol === "https:" ? parsed.toString() : null;
  } catch {
    return null;
  }
}

export function addDemoNode(graph: GraphNativeResponse, payload: NodeCreateRequest): GraphNativeResponse {
  const createdAt = new Date().toISOString();
  const id = `demo-node-${globalThis.crypto?.randomUUID?.() ?? Date.now().toString(36)}`;
  const cluster = graph.clusters[payload.kind === "link" ? 1 : graph.nodes.length % graph.clusters.length];
  const angle = graph.nodes.length * 1.37;
  const radius = 150 + (graph.nodes.length % 4) * 42;
  const anchor = [...graph.nodes].reverse().find((node) => node.cluster_id === cluster.id)
    ?? graph.nodes[graph.nodes.length - 1]
    ?? null;
  const content = payload.content_text?.trim() || payload.title?.trim() || "A new thought entered the field.";
  const node: GraphNodeRecord = {
    id,
    kind: payload.kind,
    title: payload.title?.trim() || null,
    content_text: content,
    preview_text: content.slice(0, 180),
    visibility: "private",
    created_at: createdAt,
    updated_at: createdAt,
    topics: topicsFrom(payload),
    cluster_id: cluster.id,
    cluster_label: cluster.label,
    cluster_color: cluster.color,
    connection_count: anchor ? 1 : 0,
    x: cluster.centroid_x + Math.cos(angle) * radius,
    y: cluster.centroid_y + Math.sin(angle) * radius,
    media_url: safeHttpUrl(payload.media?.url),
    link_url: safeHttpUrl(payload.link_url),
    author_id: DEMO_USER_ID,
    author_display_name: "Guest Explorer",
    relationship_to_viewer: "self",
    is_social: false,
    media_asset_id: null,
    media_kind: null,
    media_status: null,
    thumbnail_url: null,
    playback_url: null,
    duration_seconds: null,
    reply_to_node_id: payload.reply_to_node_id ?? null,
    quote_of_node_id: payload.quote_of_node_id ?? null,
  };
  const nodes = graph.nodes.map((item) =>
    item.id === anchor?.id ? { ...item, connection_count: item.connection_count + 1 } : item,
  );
  const edges = anchor
    ? [
        ...graph.edges,
        {
          id: `demo-edge-${id}`,
          source: anchor.id,
          target: id,
          edge_type: payload.reply_to_node_id ? "reply" : payload.quote_of_node_id ? "quote" : "semantic",
          weight: 0.7,
          explanation: { reason: "Created in this browser demo" },
        },
      ]
    : graph.edges;
  return {
    ...graph,
    nodes: [...nodes, node],
    edges,
    clusters: graph.clusters.map((item) =>
      item.id === cluster.id ? { ...item, node_count: item.node_count + 1 } : item,
    ),
    explanation: { reason: "Browser-local graph updated", generated_at: createdAt },
  };
}

export function searchDemoGraph(graph: GraphNativeResponse, query: string): GraphSearchResult[] {
  const normalized = query.trim().toLowerCase();
  if (!normalized) return [];
  return graph.nodes
    .filter((node) => `${node.title ?? ""} ${node.content_text ?? ""} ${node.topics.join(" ")}`.toLowerCase().includes(normalized))
    .slice(0, 12)
    .map((node, index) => ({
      node_id: node.id,
      title: node.title,
      preview_text: node.preview_text,
      cluster_label: node.cluster_label,
      cluster_color: node.cluster_color,
      score: Math.max(0.5, 1 - index * 0.05),
    }));
}

export function buildDemoThread(graph: GraphNativeResponse, nodeId: string): NodeThreadResponse | null {
  const root = graph.nodes.find((node) => node.id === nodeId);
  if (!root) return null;
  const read = (node: GraphNodeRecord): NodeRead => ({ ...node, metadata_json: { demo: true } });
  return {
    root: read(root),
    replies: graph.nodes.filter((node) => node.reply_to_node_id === root.id).map(read),
    quoted_node: root.quote_of_node_id
      ? graph.nodes.find((node) => node.id === root.quote_of_node_id)
        ? read(graph.nodes.find((node) => node.id === root.quote_of_node_id)!)
        : null
      : null,
  };
}

export function buildDemoDiscovery(graph: GraphNativeResponse, query: string): DiscoveryExploreResponse {
  const normalized = query.trim().toLowerCase();
  const candidates = graph.nodes.filter((node) =>
    normalized
      ? `${node.title ?? ""} ${node.content_text ?? ""} ${node.topics.join(" ")}`.toLowerCase().includes(normalized)
      : true,
  );
  return {
    materialization_id: "demo-discovery",
    generated_at: graph.explanation.generated_at,
    filters: { q: normalized || null, close_to_me: false, outside_my_bubble: false, high_evidence: false, new_low_spread: false, trusted_only: false, limit: 8 },
    filter_availability: { close_to_me: false, outside_my_bubble: false, high_evidence: false, new_low_spread: false, trusted_only: false },
    explanation_summary: "Ideas from this browser-local demonstration.",
    items: candidates.slice(0, 8).map((node, index) => ({
      node,
      explanation: {
        primary_reason: "demo_context",
        summary: "Shown from the local sample field; no server ranking was used.",
        matched_topics: node.topics,
        relationship_to_viewer: "self",
        signal_notes: ["browser-local demo"],
        unavailable_filters: ["social proximity", "trust signals"],
        score_breakdown: { relevance: 1 - index * 0.05, novelty: 0, trust: 0, diversity: 0, social_proximity: 0, total: 1 - index * 0.05 },
      },
    })),
  };
}
