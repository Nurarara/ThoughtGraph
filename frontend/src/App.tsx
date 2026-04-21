import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ThoughtCanvas } from "./components/ThoughtCanvas";
import type { CanvasNode, CanvasEdge, ThoughtCanvasHandle } from "./components/ThoughtCanvas";

/* ────────────────────────────────────────────
   Cluster definitions
   ──────────────────────────────────────────── */

const CLUSTER_DEFS = [
  {
    index: 0,
    label: "Technology",
    hex: "#7a9bb5",
    keywords: [
      "tech", "code", "coding", "ai", "data", "system", "systems", "software",
      "digital", "algorithm", "algorithms", "network", "networks", "machine",
      "computer", "computers", "tool", "tools", "build", "building", "engineer",
      "engineering", "program", "programming", "automation", "neural", "api",
      "model", "models", "infrastructure", "platform", "interface", "devop",
      "framework", "library", "database", "cloud", "protocol", "compute",
      "abstraction", "architecture", "implementation",
    ],
  },
  {
    index: 1,
    label: "Growth",
    hex: "#9b8abf",
    keywords: [
      "grow", "growth", "learn", "learning", "change", "improve", "improving",
      "practice", "skill", "skills", "develop", "developing", "evolve",
      "evolving", "understand", "understanding", "read", "reading", "study",
      "studying", "discipline", "habit", "habits", "progress", "mindset",
      "curiosity", "experience", "experiences", "lesson", "lessons", "insight",
      "insights", "pattern", "patterns", "reflection", "self", "identity",
      "beginner", "expert", "journey", "process",
    ],
  },
  {
    index: 2,
    label: "Purpose",
    hex: "#c4a062",
    keywords: [
      "purpose", "meaning", "value", "values", "mission", "impact", "legacy",
      "contribute", "contribution", "why", "create", "creating", "passion",
      "vision", "goal", "goals", "intention", "calling", "matter", "matters",
      "life", "work", "worth", "worthy", "important", "essence", "soul",
      "truth", "belief", "beliefs", "philosophy", "principle", "principles",
      "direction", "meaningful", "deep", "human", "humanity",
    ],
  },
];

/* ────────────────────────────────────────────
   Seed thoughts
   ──────────────────────────────────────────── */

const SEED_THOUGHTS: { content: string; cluster: number }[] = [
  // Technology
  { content: "The boundary between human intelligence and artificial intelligence is dissolving faster than we can define it.", cluster: 0 },
  { content: "Every abstraction layer we build becomes the foundation for the next breakthrough.", cluster: 0 },
  { content: "Neural networks don't think — they approximate thinking, which might be the same thing.", cluster: 0 },
  { content: "Code is the closest thing we have to pure thought made tangible.", cluster: 0 },
  { content: "The most powerful technology disappears into the background of daily life.", cluster: 0 },
  { content: "Good architecture is less about what you add and more about what you refuse to couple.", cluster: 0 },

  // Growth
  { content: "Growth isn't linear — it's a series of plateaus interrupted by sudden leaps.", cluster: 1 },
  { content: "The discomfort of not knowing is the feeling of learning.", cluster: 1 },
  { content: "Reading changes you in ways you can't predict until years later.", cluster: 1 },
  { content: "The gap between knowing and doing is where discipline lives.", cluster: 1 },
  { content: "Every expert was once a beginner who refused to stop practicing.", cluster: 1 },
  { content: "The stories we tell ourselves shape the skills we're willing to develop.", cluster: 1 },

  // Purpose
  { content: "Purpose isn't found — it's constructed from the things that consistently capture your attention.", cluster: 2 },
  { content: "Meaning emerges from the intersection of curiosity and contribution.", cluster: 2 },
  { content: "The work that matters most often feels invisible while you're doing it.", cluster: 2 },
  { content: "Legacy isn't about being remembered — it's about the cascading effects of your choices.", cluster: 2 },
  { content: "The question isn't what you want to do, but who you want to become.", cluster: 2 },
];

/* ────────────────────────────────────────────
   Local state types
   ──────────────────────────────────────────── */

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

const STORAGE_KEY = "thoughtgraph:v1";

/* ────────────────────────────────────────────
   Clustering & connection heuristics
   ──────────────────────────────────────────── */

function tokenize(text: string): string[] {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .split(/\s+/)
    .filter((w) => w.length > 2);
}

function assignCluster(text: string): number {
  const tokens = tokenize(text);
  const scores = [0, 0, 0];
  for (const t of tokens) {
    for (const cd of CLUSTER_DEFS) {
      if (cd.keywords.includes(t)) scores[cd.index] += 1;
    }
  }
  let best = -1;
  let bestScore = 0;
  for (let i = 0; i < 3; i++) {
    if (scores[i] > bestScore) {
      bestScore = scores[i];
      best = i;
    }
  }
  return best >= 0 ? best : Math.floor(Math.random() * 3);
}

function wordOverlap(a: string[], b: string[]): number {
  const setA = new Set(a);
  let overlap = 0;
  for (const w of b) if (setA.has(w)) overlap += 1;
  return overlap;
}

function detectConnections(newThought: StoredThought, existing: StoredThought[]): StoredEdge[] {
  const newTokens = tokenize(newThought.content);
  const edges: StoredEdge[] = [];
  for (const t of existing) {
    if (t.id === newThought.id) continue;
    const tTokens = tokenize(t.content);
    const overlap = wordOverlap(newTokens, tTokens);
    const sameCluster = t.clusterIndex === newThought.clusterIndex;
    const threshold = sameCluster ? 1 : 2;
    if (overlap >= threshold) {
      edges.push({
        source: newThought.id,
        target: t.id,
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

/* ────────────────────────────────────────────
   Storage
   ──────────────────────────────────────────── */

function loadStored(): { thoughts: StoredThought[]; edges: StoredEdge[] } | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed.thoughts || !parsed.edges) return null;
    return parsed;
  } catch {
    return null;
  }
}

function saveStored(data: { thoughts: StoredThought[]; edges: StoredEdge[] }) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  } catch {
    /* ignore quota errors */
  }
}

function createSeedState(): { thoughts: StoredThought[]; edges: StoredEdge[] } {
  const now = Date.now();
  const thoughts: StoredThought[] = SEED_THOUGHTS.map((s, i) => ({
    id: generateId(),
    content: s.content,
    clusterIndex: s.cluster,
    createdAt: new Date(now - (SEED_THOUGHTS.length - i) * 3 * 60 * 60 * 1000).toISOString(),
  }));
  const edges: StoredEdge[] = [];
  for (let i = 0; i < thoughts.length; i++) {
    const newEdges = detectConnections(thoughts[i], thoughts.slice(0, i));
    edges.push(...newEdges);
  }
  return { thoughts, edges };
}

/* ────────────────────────────────────────────
   Helpers
   ──────────────────────────────────────────── */

function relativeTime(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  const sec = Math.floor(ms / 1000);
  if (sec < 60) return "just now";
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min} minute${min === 1 ? "" : "s"} ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr} hour${hr === 1 ? "" : "s"} ago`;
  const day = Math.floor(hr / 24);
  return `${day} day${day === 1 ? "" : "s"} ago`;
}

/* ────────────────────────────────────────────
   App
   ──────────────────────────────────────────── */

export default function App() {
  const [state, setState] = useState<{ thoughts: StoredThought[]; edges: StoredEdge[] }>(() => {
    const stored = loadStored();
    return stored ?? createSeedState();
  });

  const [selected, setSelected] = useState<CanvasNode | null>(null);
  const [inputValue, setInputValue] = useState("");

  const canvasHandleRef = useRef<ThoughtCanvasHandle>(null);
  const detailCardRef = useRef<HTMLDivElement>(null);

  // Persist on every change
  useEffect(() => {
    saveStored(state);
  }, [state]);

  // Compute canvas nodes/edges
  const canvasData = useMemo(() => {
    const connectionCount = new Map<string, number>();
    for (const e of state.edges) {
      connectionCount.set(e.source, (connectionCount.get(e.source) ?? 0) + 1);
      connectionCount.set(e.target, (connectionCount.get(e.target) ?? 0) + 1);
    }
    const nodes: CanvasNode[] = state.thoughts.map((t) => ({
      id: t.id,
      content: t.content,
      clusterIndex: t.clusterIndex,
      clusterLabel: CLUSTER_DEFS[t.clusterIndex % 3].label,
      connectionCount: connectionCount.get(t.id) ?? 0,
      createdAt: t.createdAt,
    }));
    const edges: CanvasEdge[] = state.edges.map((e) => ({
      source: e.source,
      target: e.target,
      weight: e.weight,
    }));
    return { nodes, edges };
  }, [state]);

  // Track selected node position via RAF so the card follows the node
  useEffect(() => {
    if (!selected) return;
    let frame = 0;
    let running = true;

    const loop = () => {
      if (!running) return;
      const pos = canvasHandleRef.current?.getNodeScreenPosition(selected.id);
      const card = detailCardRef.current;
      if (pos && card) {
        const cardWidth = 280;
        const cardHeight = card.offsetHeight || 140;
        const vw = window.innerWidth;
        const vh = window.innerHeight;
        const margin = 24;

        // Prefer placing card to the right of the node, offset down slightly
        let cx = pos.x + 40;
        let cy = pos.y - 16;

        // Flip to left if it would overflow right edge
        if (cx + cardWidth + margin > vw) {
          cx = pos.x - cardWidth - 40;
        }
        // Clamp vertically
        if (cy + cardHeight + margin > vh) {
          cy = vh - cardHeight - margin;
        }
        if (cy < margin) cy = margin;
        // Clamp horizontally as fallback
        if (cx < margin) cx = margin;

        card.style.transform = `translate(${cx}px, ${cy}px)`;
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
    if (!selected) return 0;
    return canvasData.nodes.find((n) => n.id === selected.id)?.connectionCount ?? 0;
  }, [selected, canvasData]);

  const handleSubmit = useCallback(
    (event: FormEvent) => {
      event.preventDefault();
      const content = inputValue.trim();
      if (!content) return;

      const newThought: StoredThought = {
        id: generateId(),
        content,
        clusterIndex: assignCluster(content),
        createdAt: new Date().toISOString(),
      };

      const newEdges = detectConnections(newThought, state.thoughts);

      setState((prev) => ({
        thoughts: [...prev.thoughts, newThought],
        edges: [...prev.edges, ...newEdges],
      }));

      setInputValue("");
    },
    [inputValue, state.thoughts]
  );

  const isEmpty = state.thoughts.length === 0;
  const selectedCluster = selected ? CLUSTER_DEFS[selected.clusterIndex % 3] : null;

  return (
    <div className="app-shell">
      <div className="canvas-layer">
        <ThoughtCanvas
          ref={canvasHandleRef}
          nodes={canvasData.nodes}
          edges={canvasData.edges}
          selectedNodeId={selected?.id ?? null}
          onSelectNode={setSelected}
          onHoverNode={() => { /* hover state not currently surfaced in UI */ }}
        />
      </div>

      {/* Watermark */}
      <div className="watermark">
        <div className="watermark-title">ThoughtGraph</div>
        <div className="watermark-subtitle">your mind, visualised</div>
      </div>

      {/* Node count */}
      <div className="node-count">
        {String(state.thoughts.length).padStart(3, "0")} nodes
      </div>

      {/* Legend */}
      <div className="legend">
        {CLUSTER_DEFS.map((c) => (
          <div className="legend-item" key={c.label}>
            <div className="legend-ring" style={{ borderColor: c.hex }} />
            <div className="legend-label">{c.label}</div>
          </div>
        ))}
      </div>

      {/* Selected detail card — always rendered when selected; position updated via RAF */}
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

      {/* Seed button if empty */}
      {isEmpty ? (
        <button className="seed-button" onClick={() => setState(createSeedState())}>
          initialize graph
        </button>
      ) : null}

      {/* Input */}
      <form className="thought-input-wrap" onSubmit={handleSubmit}>
        <input
          className="thought-input"
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.currentTarget.value)}
          placeholder="what are you thinking?"
          autoComplete="off"
          spellCheck={false}
        />
      </form>
    </div>
  );
}
