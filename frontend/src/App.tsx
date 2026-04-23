import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ArchiveDrawer } from "./components/ArchiveDrawer";
import { AuthScreen } from "./components/AuthScreen";
import { ExploreDrawer } from "./components/ExploreDrawer";
import { FriendsPanel } from "./components/FriendsPanel";
import { NotificationsBell } from "./components/NotificationsBell";
import { PostComposer } from "./components/PostComposer";
import { ProfileSheet } from "./components/ProfileSheet";
import { ThoughtCanvas } from "./components/ThoughtCanvas";
import type { CanvasEdge, CanvasNode, ThoughtCanvasHandle } from "./components/ThoughtCanvas";
import { TopicFeed } from "./components/TopicFeed";
import type {
  ClusterKey,
  FriendOverlayNode,
  GraphResponse,
  SerendipityResponse,
  SessionPayload,
  SnapshotRead,
  TrendingCluster,
  UserProfile,
  WeeklyReport,
} from "./lib/apiClient";
import { clearSession, loadSession, thoughtApi } from "./lib/apiClient";

const CLUSTER_DEFS = [
  {
    index: 0,
    key: "technology" as ClusterKey,
    label: "Technology",
    hex: "#7a9bb5",
    keywords: [
      "tech", "code", "coding", "ai", "data", "system", "systems", "software",
      "digital", "algorithm", "algorithms", "network", "networks", "machine",
      "computer", "computers", "tool", "tools", "build", "building", "engineer",
      "engineering", "program", "programming", "automation", "neural", "api",
      "model", "models", "infrastructure", "platform", "interface", "framework",
      "library", "database", "cloud", "protocol", "compute", "architecture",
    ],
  },
  {
    index: 1,
    key: "growth" as ClusterKey,
    label: "Growth",
    hex: "#9b8abf",
    keywords: [
      "grow", "growth", "learn", "learning", "change", "improve", "practice",
      "skill", "skills", "develop", "evolve", "understand", "reading", "study",
      "discipline", "habit", "progress", "mindset", "curiosity", "experience",
      "lesson", "insight", "pattern", "reflection", "identity", "journey",
      "process", "health", "routine", "sleep",
    ],
  },
  {
    index: 2,
    key: "purpose" as ClusterKey,
    label: "Purpose",
    hex: "#c4a062",
    keywords: [
      "purpose", "meaning", "value", "mission", "impact", "legacy", "contribute",
      "why", "create", "passion", "vision", "goal", "intention", "calling",
      "matter", "life", "work", "worthy", "truth", "belief", "philosophy",
      "principle", "direction", "human", "trust", "freedom",
    ],
  },
];

const CLUSTER_BY_KEY: Record<ClusterKey, typeof CLUSTER_DEFS[number]> = {
  technology: CLUSTER_DEFS[0],
  growth: CLUSTER_DEFS[1],
  purpose: CLUSTER_DEFS[2],
};

const SEED_THOUGHTS: { content: string; cluster: number }[] = [
  { content: "The boundary between human intelligence and artificial intelligence is dissolving faster than we can define it.", cluster: 0 },
  { content: "Every abstraction layer we build becomes the foundation for the next breakthrough.", cluster: 0 },
  { content: "Neural networks do not think, but they still change how thought gets externalized.", cluster: 0 },
  { content: "Code is the closest thing we have to pure thought made tangible.", cluster: 0 },
  { content: "The most powerful technology disappears into the background of daily life.", cluster: 0 },
  { content: "Growth is not linear. It is a series of plateaus interrupted by sudden leaps.", cluster: 1 },
  { content: "The discomfort of not knowing is the feeling of learning.", cluster: 1 },
  { content: "Reading changes you in ways you cannot predict until years later.", cluster: 1 },
  { content: "The gap between knowing and doing is where discipline lives.", cluster: 1 },
  { content: "Purpose is not found. It is constructed from the things that keep reclaiming your attention.", cluster: 2 },
  { content: "Meaning emerges from the intersection of curiosity and contribution.", cluster: 2 },
  { content: "Legacy is the cascading effect of your choices long after the moment has passed.", cluster: 2 },
];

interface StoredThought {
  id: string;
  content: string;
  clusterIndex: number;
  createdAt: string;
}

interface StoredEdge {
  source: string;
  target: string;
  weight: number;
}

interface BridgeCard {
  id: string;
  userId: string;
  displayName: string;
  cluster: ClusterKey;
  score: number;
  postCount: number;
  thoughtCount: number;
  thoughts: StoredThought[];
}

const STORAGE_KEY = "thoughtgraph:v1";

function tokenize(text: string): string[] {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .split(/\s+/)
    .filter((word) => word.length > 2);
}

function assignCluster(text: string): number {
  const tokens = tokenize(text);
  const scores = [0, 0, 0];
  for (const token of tokens) {
    for (const cluster of CLUSTER_DEFS) {
      if (cluster.keywords.includes(token)) {
        scores[cluster.index] += 1;
      }
    }
  }
  let bestIndex = 0;
  let bestScore = -1;
  for (let index = 0; index < scores.length; index += 1) {
    if (scores[index] > bestScore) {
      bestScore = scores[index];
      bestIndex = index;
    }
  }
  return bestScore <= 0 ? Math.floor(Math.random() * 3) : bestIndex;
}

function wordOverlap(a: string[], b: string[]): number {
  const setA = new Set(a);
  let overlap = 0;
  for (const token of b) {
    if (setA.has(token)) {
      overlap += 1;
    }
  }
  return overlap;
}

function detectConnections(newThought: StoredThought, existing: StoredThought[]): StoredEdge[] {
  const newTokens = tokenize(newThought.content);
  const edges: StoredEdge[] = [];
  for (const thought of existing) {
    if (thought.id === newThought.id) {
      continue;
    }
    const overlap = wordOverlap(newTokens, tokenize(thought.content));
    const sameCluster = thought.clusterIndex === newThought.clusterIndex;
    const threshold = sameCluster ? 1 : 2;
    if (overlap >= threshold) {
      edges.push({
        source: newThought.id,
        target: thought.id,
        weight: Math.min(1, overlap / 6) + (sameCluster ? 0.2 : 0),
      });
    }
  }
  edges.sort((a, b) => b.weight - a.weight);
  return edges.slice(0, 4);
}

function generateId(): string {
  return `t_${Math.random().toString(36).slice(2, 10)}_${Date.now().toString(36)}`;
}

function loadStored(): { thoughts: StoredThought[]; edges: StoredEdge[] } | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as { thoughts?: StoredThought[]; edges?: StoredEdge[] };
    if (!parsed.thoughts || !parsed.edges) {
      return null;
    }
    return { thoughts: parsed.thoughts, edges: parsed.edges };
  } catch {
    return null;
  }
}

function saveStored(data: { thoughts: StoredThought[]; edges: StoredEdge[] }) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  } catch {
    // Ignore quota errors.
  }
}

function createSeedState(): { thoughts: StoredThought[]; edges: StoredEdge[] } {
  const now = Date.now();
  const thoughts = SEED_THOUGHTS.map((seed, index) => ({
    id: generateId(),
    content: seed.content,
    clusterIndex: seed.cluster,
    createdAt: new Date(now - (SEED_THOUGHTS.length - index) * 2 * 60 * 60 * 1000).toISOString(),
  }));
  const edges: StoredEdge[] = [];
  for (let index = 0; index < thoughts.length; index += 1) {
    edges.push(...detectConnections(thoughts[index], thoughts.slice(0, index)));
  }
  return { thoughts, edges };
}

function relativeTime(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  const sec = Math.floor(ms / 1000);
  if (sec < 60) {
    return "just now";
  }
  const min = Math.floor(sec / 60);
  if (min < 60) {
    return `${min} minute${min === 1 ? "" : "s"} ago`;
  }
  const hr = Math.floor(min / 60);
  if (hr < 24) {
    return `${hr} hour${hr === 1 ? "" : "s"} ago`;
  }
  const day = Math.floor(hr / 24);
  return `${day} day${day === 1 ? "" : "s"} ago`;
}

function mapGraphToStoredState(graph: GraphResponse): { thoughts: StoredThought[]; edges: StoredEdge[] } {
  return {
    thoughts: graph.nodes.map((node) => ({
      id: node.id,
      content: node.content,
      clusterIndex: assignCluster(`${node.cluster_label ?? ""} ${node.content} ${node.topics.join(" ")}`),
      createdAt: node.created_at,
    })),
    edges: graph.edges.map((edge) => ({
      source: edge.source,
      target: edge.target,
      weight: edge.weight,
    })),
  };
}

export default function App() {
  const [localState, setLocalState] = useState<{ thoughts: StoredThought[]; edges: StoredEdge[] }>(() => {
    const stored = loadStored();
    return stored ?? createSeedState();
  });
  const [remoteGraph, setRemoteGraph] = useState<GraphResponse | null>(null);
  const [selected, setSelected] = useState<CanvasNode | null>(null);
  const [inputValue, setInputValue] = useState("");

  const [session, setSession] = useState<SessionPayload | null>(() => loadSession());
  const [authOpen, setAuthOpen] = useState(false);
  const [friendsOpen, setFriendsOpen] = useState(false);
  const [composerOpen, setComposerOpen] = useState(false);
  const [composerCluster, setComposerCluster] = useState<ClusterKey | undefined>(undefined);
  const [feedCluster, setFeedCluster] = useState<ClusterKey | null>(null);
  const [feedOpen, setFeedOpen] = useState(false);
  const [profileUserId, setProfileUserId] = useState<string | null>(null);
  const [exploreOpen, setExploreOpen] = useState(false);
  const [archiveOpen, setArchiveOpen] = useState(false);

  const [friendOverlay, setFriendOverlay] = useState<FriendOverlayNode[]>([]);
  const [meProfile, setMeProfile] = useState<UserProfile | null>(null);
  const [trendingClusters, setTrendingClusters] = useState<TrendingCluster[]>([]);
  const [publicSnapshots, setPublicSnapshots] = useState<SnapshotRead[]>([]);
  const [snapshots, setSnapshots] = useState<SnapshotRead[]>([]);
  const [reports, setReports] = useState<WeeklyReport[]>([]);
  const [latestReport, setLatestReport] = useState<WeeklyReport | null>(null);
  const [serendipity, setSerendipity] = useState<SerendipityResponse | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [bridgeFocus, setBridgeFocus] = useState<BridgeCard | null>(null);

  const canvasHandleRef = useRef<ThoughtCanvasHandle>(null);
  const detailCardRef = useRef<HTMLDivElement>(null);
  const importedUsersRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    saveStored(localState);
  }, [localState]);

  const refreshOverlay = useCallback(async () => {
    if (!session) {
      setFriendOverlay([]);
      return;
    }
    try {
      const response = await thoughtApi.getFriendsOverlay();
      setFriendOverlay(response.nodes);
    } catch {
      setFriendOverlay([]);
    }
  }, [session]);

  const refreshRemoteGraph = useCallback(async () => {
    if (!session) {
      setRemoteGraph(null);
      return;
    }
    setSyncing(true);
    try {
      let graph = await thoughtApi.getGraph();
      const shouldImportLocal =
        graph.nodes.length === 0 &&
        localState.thoughts.length > 0 &&
        !importedUsersRef.current.has(session.user_id);

      if (shouldImportLocal) {
        importedUsersRef.current.add(session.user_id);
        for (const thought of localState.thoughts) {
          await thoughtApi.createThought({ content: thought.content, visibility: "private" });
        }
        graph = await thoughtApi.getGraph();
      }
      setRemoteGraph(graph);
    } catch {
      setRemoteGraph(null);
    } finally {
      setSyncing(false);
    }
  }, [localState.thoughts, session]);

  const refreshSocial = useCallback(async () => {
    if (!session) {
      setMeProfile(null);
      setTrendingClusters([]);
      setPublicSnapshots([]);
      setSnapshots([]);
      setReports([]);
      setLatestReport(null);
      setSerendipity(null);
      return;
    }
    try {
      const [
        me,
        trending,
        recentPublic,
        ownSnapshots,
        ownReports,
        latest,
        serendipityResponse,
      ] = await Promise.all([
        thoughtApi.getMe(),
        thoughtApi.getTrendingClusters(),
        thoughtApi.getRecentPublicSnapshots(),
        thoughtApi.getSnapshots(),
        thoughtApi.getReports(),
        thoughtApi.getLatestReport().catch(() => null),
        thoughtApi.getSerendipity(),
      ]);
      setMeProfile(me);
      setTrendingClusters(trending);
      setPublicSnapshots(recentPublic);
      setSnapshots(ownSnapshots);
      setReports(ownReports);
      setLatestReport(latest ?? ownReports[0] ?? null);
      setSerendipity(serendipityResponse);
    } catch {
      // Keep the shell usable even if social surfaces fail independently.
    }
  }, [session]);

  useEffect(() => {
    void refreshOverlay();
    void refreshRemoteGraph();
    void refreshSocial();
  }, [refreshOverlay, refreshRemoteGraph, refreshSocial]);

  const activeState = useMemo(() => {
    if (session && remoteGraph) {
      return mapGraphToStoredState(remoteGraph);
    }
    return localState;
  }, [localState, remoteGraph, session]);

  useEffect(() => {
    if (!selected) {
      return;
    }
    if (!activeState.thoughts.some((thought) => thought.id === selected.id)) {
      setSelected(null);
    }
  }, [activeState.thoughts, selected]);

  const canvasData = useMemo(() => {
    const connectionCount = new Map<string, number>();
    for (const edge of activeState.edges) {
      connectionCount.set(edge.source, (connectionCount.get(edge.source) ?? 0) + 1);
      connectionCount.set(edge.target, (connectionCount.get(edge.target) ?? 0) + 1);
    }
    const nodes: CanvasNode[] = activeState.thoughts.map((thought) => ({
      id: thought.id,
      content: thought.content,
      clusterIndex: thought.clusterIndex,
      clusterLabel: CLUSTER_DEFS[thought.clusterIndex % 3].label,
      connectionCount: connectionCount.get(thought.id) ?? 0,
      createdAt: thought.createdAt,
    }));
    const edges: CanvasEdge[] = activeState.edges.map((edge) => ({
      source: edge.source,
      target: edge.target,
      weight: edge.weight,
    }));
    return { nodes, edges };
  }, [activeState]);

  useEffect(() => {
    if (!selected) {
      return;
    }
    let frame = 0;
    let running = true;

    const loop = () => {
      if (!running) {
        return;
      }
      const pos = canvasHandleRef.current?.getNodeScreenPosition(selected.id);
      const card = detailCardRef.current;
      if (pos && card) {
        const cardWidth = 300;
        const cardHeight = card.offsetHeight || 160;
        const margin = 24;
        let left = pos.x + 40;
        let top = pos.y - 16;

        if (left + cardWidth + margin > window.innerWidth) {
          left = pos.x - cardWidth - 40;
        }
        if (top + cardHeight + margin > window.innerHeight) {
          top = window.innerHeight - cardHeight - margin;
        }
        if (top < margin) {
          top = margin;
        }
        if (left < margin) {
          left = margin;
        }
        card.style.transform = `translate(${left}px, ${top}px)`;
      }
      frame = requestAnimationFrame(loop);
    };

    loop();
    return () => {
      running = false;
      cancelAnimationFrame(frame);
    };
  }, [selected]);

  const selectedConnectionCount = useMemo(() => {
    if (!selected) {
      return 0;
    }
    return canvasData.nodes.find((node) => node.id === selected.id)?.connectionCount ?? 0;
  }, [canvasData.nodes, selected]);

  const handleSubmit = useCallback(
    async (event: FormEvent) => {
      event.preventDefault();
      const content = inputValue.trim();
      if (!content) {
        return;
      }

      if (session) {
        await thoughtApi.createThought({ content, visibility: "private" });
        await refreshRemoteGraph();
        await refreshSocial();
      } else {
        const newThought: StoredThought = {
          id: generateId(),
          content,
          clusterIndex: assignCluster(content),
          createdAt: new Date().toISOString(),
        };
        const newEdges = detectConnections(newThought, localState.thoughts);
        setLocalState((prev) => ({
          thoughts: [...prev.thoughts, newThought],
          edges: [...prev.edges, ...newEdges],
        }));
      }

      setInputValue("");
    },
    [inputValue, localState.thoughts, refreshRemoteGraph, refreshSocial, session],
  );

  const handleLogout = async () => {
    try {
      await thoughtApi.logout();
    } catch {
      // Best effort only.
    }
    clearSession();
    setSession(null);
    setRemoteGraph(null);
    setMeProfile(null);
    setSerendipity(null);
    setBridgeFocus(null);
  };

  const handleToggleSerendipity = async (enabled: boolean) => {
    await thoughtApi.updateDiscoverySettings(enabled);
    await refreshSocial();
  };

  const handleCaptureSnapshot = async () => {
    if (!session) {
      return;
    }
    setSyncing(true);
    try {
      await thoughtApi.createSnapshot("my current mental state", true);
      await refreshSocial();
    } finally {
      setSyncing(false);
    }
  };

  const handleGenerateReport = async () => {
    if (!session) {
      return;
    }
    setSyncing(true);
    try {
      await thoughtApi.generateWeeklyReport();
      await refreshSocial();
    } finally {
      setSyncing(false);
    }
  };

  const bridgeCards = useMemo(() => {
    const countsByCluster = new Map<ClusterKey, number>();
    const thoughtsByCluster = new Map<ClusterKey, StoredThought[]>();
    for (const thought of activeState.thoughts) {
      const cluster = CLUSTER_DEFS[thought.clusterIndex % 3].key;
      countsByCluster.set(cluster, (countsByCluster.get(cluster) ?? 0) + 1);
      thoughtsByCluster.set(cluster, [...(thoughtsByCluster.get(cluster) ?? []), thought]);
    }

    return friendOverlay
      .map((overlayNode) => {
        const thoughtCount = countsByCluster.get(overlayNode.cluster_key) ?? 0;
        if (thoughtCount === 0) {
          return null;
        }
        return {
          id: overlayNode.id,
          userId: overlayNode.id.split(":")[0],
          displayName: overlayNode.display_name,
          cluster: overlayNode.cluster_key,
          score: Math.min(100, thoughtCount * 14 + overlayNode.post_count * 11),
          postCount: overlayNode.post_count,
          thoughtCount,
          thoughts: (thoughtsByCluster.get(overlayNode.cluster_key) ?? [])
            .slice()
            .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
            .slice(0, 3),
        } satisfies BridgeCard;
      })
      .filter((bridge): bridge is BridgeCard => bridge !== null)
      .sort((a, b) => b.score - a.score)
      .slice(0, 6);
  }, [activeState.thoughts, friendOverlay]);

  const isEmpty = activeState.thoughts.length === 0;
  const selectedCluster = selected ? CLUSTER_DEFS[selected.clusterIndex % 3] : null;
  const signedIn = session !== null;
  const userInitial = session?.display_name?.[0]?.toUpperCase() ?? "";

  return (
    <div className="app-shell">
      <div className="canvas-layer">
        <ThoughtCanvas
          ref={canvasHandleRef}
          nodes={canvasData.nodes}
          edges={canvasData.edges}
          selectedNodeId={selected?.id ?? null}
          onSelectNode={setSelected}
          onHoverNode={() => undefined}
        />
      </div>

      <div className="watermark">
        <div className="watermark-title">ThoughtGraph</div>
        <div className="watermark-subtitle">topic-centric social introspection</div>
      </div>

      <div className="topbar">
        <div className="node-count" style={{ position: "static", opacity: 0.35 }}>
          {String(activeState.thoughts.length).padStart(3, "0")} nodes
        </div>
        {syncing ? <div className="topbar-pill">syncing</div> : null}
        {signedIn && meProfile?.serendipity_enabled ? <div className="topbar-pill">serendipity</div> : null}
        {signedIn ? (
          <>
            <button className="topbar-button" onClick={() => setExploreOpen(true)}>
              explore
            </button>
            <button className="topbar-button" onClick={() => setArchiveOpen(true)}>
              archive
            </button>
            <button className="topbar-button primary" title="share to a topic" onClick={() => setComposerOpen(true)}>
              +
            </button>
            <NotificationsBell onOpenProfile={setProfileUserId} />
            <button className="topbar-button" onClick={() => setFriendsOpen(true)}>
              friends
            </button>
            <button className="topbar-user" title={session?.email ?? ""} onClick={() => setProfileUserId(session.user_id)}>
              {userInitial || "me"}
            </button>
            <button className="topbar-button muted" onClick={handleLogout} title="sign out">
              out
            </button>
          </>
        ) : (
          <button className="topbar-button" onClick={() => setAuthOpen(true)}>
            sign in
          </button>
        )}
      </div>

      <div className="legend">
        {CLUSTER_DEFS.map((cluster) => (
          <div
            className={`legend-item ${signedIn ? "interactive" : ""}`}
            key={cluster.key}
            onClick={signedIn ? () => {
              setFeedCluster(cluster.key);
              setFeedOpen(true);
            } : undefined}
            title={signedIn ? `open ${cluster.label.toLowerCase()} feed` : undefined}
          >
            <div className="legend-ring" style={{ borderColor: cluster.hex }} />
            <div className="legend-label">{cluster.label}</div>
          </div>
        ))}
      </div>

      {signedIn && friendOverlay.length > 0 ? (
        <div className="friend-ghost-row">
          <div className="friend-ghost-heading">friend layers</div>
          {friendOverlay.slice(0, 8).map((ghost) => {
            const cluster = CLUSTER_BY_KEY[ghost.cluster_key];
            return (
              <div className="friend-ghost" key={ghost.id} style={{ borderColor: cluster.hex }}>
                <div className="friend-ghost-dot" style={{ background: cluster.hex }} />
                <span>{ghost.display_name}</span>
                <span style={{ color: cluster.hex }}>
                  {ghost.post_count} {cluster.label.toLowerCase()}
                </span>
              </div>
            );
          })}
        </div>
      ) : null}

      {signedIn && bridgeCards.length > 0 ? (
        <div className="bridge-row">
          <div className="bridge-heading">live bridges</div>
          {bridgeCards.map((bridge) => (
            <button
              key={bridge.id}
              className="bridge-chip"
              onClick={() => setBridgeFocus(bridge)}
              style={{ borderColor: CLUSTER_BY_KEY[bridge.cluster].hex }}
            >
              <span>{bridge.displayName}</span>
              <strong>{bridge.score}</strong>
              <small>{CLUSTER_BY_KEY[bridge.cluster].label.toLowerCase()}</small>
            </button>
          ))}
        </div>
      ) : null}

      {bridgeFocus ? (
        <div className="bridge-panel">
          <div className="bridge-panel-header">
            <div>
              <div className="drawer-label">overlap bridge</div>
              <div className="bridge-panel-title">
                {bridgeFocus.displayName} x {CLUSTER_BY_KEY[bridgeFocus.cluster].label}
              </div>
            </div>
            <button className="drawer-close" onClick={() => setBridgeFocus(null)}>
              x
            </button>
          </div>
          <div className="bridge-panel-copy">
            {bridgeFocus.thoughtCount} of your thoughts overlap with {bridgeFocus.postCount} friend posts in this cluster.
          </div>
          <div className="bridge-thoughts">
            {bridgeFocus.thoughts.map((thought) => (
              <div key={thought.id} className="bridge-thought-card">
                <p>{thought.content}</p>
                <span>{relativeTime(thought.createdAt)}</span>
              </div>
            ))}
          </div>
          <div className="bridge-actions">
            <button
              className="drawer-action"
              onClick={() => {
                setFeedCluster(bridgeFocus.cluster);
                setFeedOpen(true);
              }}
            >
              open topic feed
            </button>
            <button className="drawer-action" onClick={() => setProfileUserId(bridgeFocus.userId)}>
              open profile
            </button>
          </div>
        </div>
      ) : null}

      {selected && selectedCluster ? (
        <div
          ref={detailCardRef}
          className="detail-card"
          style={{
            borderColor: selectedCluster.hex,
            top: 0,
            left: 0,
          }}
        >
          <div className="detail-card-content">{selected.content}</div>
          <div className="detail-card-meta">
            <span className="detail-card-cluster" style={{ color: selectedCluster.hex }}>
              {selectedCluster.label}
            </span>
            <span>
              {selectedConnectionCount} connection{selectedConnectionCount === 1 ? "" : "s"}
            </span>
            <span>created {relativeTime(selected.createdAt)}</span>
          </div>
        </div>
      ) : null}

      {isEmpty ? (
        <button className="seed-button" onClick={() => setLocalState(createSeedState())}>
          initialize graph
        </button>
      ) : null}

      <form className="thought-input-wrap" onSubmit={(event) => void handleSubmit(event)}>
        <input
          className="thought-input"
          type="text"
          value={inputValue}
          onChange={(event) => setInputValue(event.currentTarget.value)}
          placeholder={signedIn ? "what are you thinking? (saved privately by default)" : "what are you thinking?"}
          autoComplete="off"
          spellCheck={false}
        />
      </form>

      {authOpen ? (
        <AuthScreen
          onAuthenticated={(nextSession) => {
            setSession(nextSession);
            setAuthOpen(false);
          }}
          onClose={() => setAuthOpen(false)}
        />
      ) : null}

      <FriendsPanel
        open={friendsOpen}
        onClose={() => setFriendsOpen(false)}
        onFriendsChanged={() => {
          void refreshOverlay();
          void refreshSocial();
        }}
        onOpenProfile={setProfileUserId}
      />

      <PostComposer
        open={composerOpen}
        initialCluster={composerCluster}
        onClose={() => setComposerOpen(false)}
        onCreated={() => {
          void refreshOverlay();
          void refreshSocial();
        }}
      />

      <TopicFeed
        open={feedOpen}
        cluster={feedCluster}
        currentUserId={session?.user_id ?? null}
        onClose={() => setFeedOpen(false)}
        onCompose={(cluster) => {
          setComposerCluster(cluster);
          setComposerOpen(true);
        }}
        onOpenProfile={setProfileUserId}
      />

      <ProfileSheet
        userId={profileUserId}
        onClose={() => setProfileUserId(null)}
        onFriendsChanged={() => {
          void refreshOverlay();
          void refreshSocial();
        }}
      />

      <ExploreDrawer
        open={exploreOpen}
        trending={trendingClusters}
        publicSnapshots={publicSnapshots}
        serendipity={serendipity}
        busy={syncing}
        onClose={() => setExploreOpen(false)}
        onToggleSerendipity={(enabled) => void handleToggleSerendipity(enabled)}
        onOpenFeed={(cluster) => {
          setFeedCluster(cluster);
          setFeedOpen(true);
          setExploreOpen(false);
        }}
      />

      <ArchiveDrawer
        open={archiveOpen}
        snapshots={snapshots}
        reports={reports}
        latestReport={latestReport}
        busy={syncing}
        onClose={() => setArchiveOpen(false)}
        onCaptureSnapshot={() => void handleCaptureSnapshot()}
        onGenerateReport={() => void handleGenerateReport()}
      />
    </div>
  );
}
