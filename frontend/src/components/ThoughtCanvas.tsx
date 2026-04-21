import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef } from "react";

/* ────────────────────────────────────────────
   Types
   ──────────────────────────────────────────── */

export interface CanvasNode {
  id: string;
  content: string;
  clusterIndex: number;
  clusterLabel: string;
  connectionCount: number;
  createdAt: string;
}

export interface CanvasEdge {
  source: string;
  target: string;
  weight: number;
}

interface Props {
  nodes: CanvasNode[];
  edges: CanvasEdge[];
  selectedNodeId: string | null;
  onSelectNode: (node: CanvasNode | null) => void;
  onHoverNode: (node: CanvasNode | null) => void;
}

export interface ThoughtCanvasHandle {
  getNodeScreenPosition: (id: string) => { x: number; y: number } | null;
}

/* ────────────────────────────────────────────
   Constants
   ──────────────────────────────────────────── */

const CLUSTER_COLORS: [number, number, number][] = [
  [122, 155, 181], // Technology — steel blue
  [155, 138, 191], // Growth — soft violet
  [196, 160, 98],  // Purpose — warm amber
];

const BG_COLOR = "#f5f3ef";

// Physics
const CLUSTER_GRAVITY = 0.0028;
const REPULSION = 420;
const EDGE_SPRING = 0.008;
const EDGE_REST = 90;
const DAMPING = 0.91;
const GLOBAL_ROTATION_SPEED = (2 * Math.PI) / (140 * 60); // ~140s full cycle at 60fps
const CLUSTER_RADIUS_RATIO = 0.2; // fraction of min(w,h)

// Rendering
const DORMANT_RADIUS = 2.8;
const DORMANT_RING = 5;
const EXPANDED_RADIUS = 8;
const RING_COUNT = 4;
const RING_SPACING = 8;
const PARTICLE_SPEED = 0.0012;
const PARTICLE_RADIUS = 1.6;
const PHANTOM_INTERVAL = 4000; // ms between phantom connections
const FLICKER_INTERVAL = 2200;

/* ────────────────────────────────────────────
   Internal sim types
   ──────────────────────────────────────────── */

interface SimNode {
  id: string;
  content: string;
  clusterIndex: number;
  clusterLabel: string;
  connectionCount: number;
  createdAt: string;
  x: number;
  y: number;
  vx: number;
  vy: number;
  expand: number;       // 0 = dormant, 1 = fully expanded
  targetExpand: number;
  jitterPhase: number;
  jitterSpeed: number;
  birthTime: number;
  birthDone: boolean;
}

interface SimEdge {
  sourceId: string;
  targetId: string;
  weight: number;
  isCross: boolean;
  particleOffset: number;
  stitchProgress: number; // 0-1 for new-connection animation
}

interface PhantomEdge {
  x1: number; y1: number;
  x2: number; y2: number;
  life: number; // 0-1
  maxLife: number;
}

interface SignalFlicker {
  x: number; y: number;
  life: number;
  maxLife: number;
}

/* ────────────────────────────────────────────
   Helpers
   ──────────────────────────────────────────── */

function rgba(c: [number, number, number], a: number) {
  return `rgba(${c[0]},${c[1]},${c[2]},${a})`;
}

function lerpColor(a: [number, number, number], b: [number, number, number], t: number): [number, number, number] {
  return [
    a[0] + (b[0] - a[0]) * t,
    a[1] + (b[1] - a[1]) * t,
    a[2] + (b[2] - a[2]) * t,
  ];
}

function dist(x1: number, y1: number, x2: number, y2: number) {
  return Math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2);
}

function lerp(a: number, b: number, t: number) {
  return a + (b - a) * t;
}

/* ────────────────────────────────────────────
   Component
   ──────────────────────────────────────────── */

export const ThoughtCanvas = forwardRef<ThoughtCanvasHandle, Props>(function ThoughtCanvas(
  { nodes, edges, selectedNodeId, onSelectNode, onHoverNode },
  ref
) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useImperativeHandle(
    ref,
    () => ({
      getNodeScreenPosition(id: string) {
        const s = sim.current;
        const n = s.nodeMap.get(id);
        if (!n) return null;
        const jx = n.x + Math.sin(s.time * n.jitterSpeed + n.jitterPhase) * 1.2;
        const jy = n.y + Math.cos(s.time * n.jitterSpeed * 1.3 + n.jitterPhase) * 1.2;
        return { x: jx, y: jy };
      },
    }),
    []
  );

  // All mutable simulation state lives in this ref for performance
  const sim = useRef<{
    nodes: SimNode[];
    edges: SimEdge[];
    nodeMap: Map<string, SimNode>;
    adjacency: Map<string, Set<string>>;
    phantoms: PhantomEdge[];
    flickers: SignalFlicker[];
    width: number;
    height: number;
    dpr: number;
    rotation: number;
    time: number;
    hoveredId: string | null;
    selectedId: string | null;
    mouseX: number;
    mouseY: number;
    lastPhantomTime: number;
    lastFlickerTime: number;
    prevNodeIds: Set<string>;
    frameId: number;
  }>({
    nodes: [],
    edges: [],
    nodeMap: new Map(),
    adjacency: new Map(),
    phantoms: [],
    flickers: [],
    width: 0,
    height: 0,
    dpr: 1,
    rotation: 0,
    time: 0,
    hoveredId: null,
    selectedId: null,
    mouseX: -9999,
    mouseY: -9999,
    lastPhantomTime: 0,
    lastFlickerTime: 0,
    prevNodeIds: new Set(),
    frameId: 0,
  });

  // Keep selectedId in sync
  useEffect(() => {
    sim.current.selectedId = selectedNodeId;
  }, [selectedNodeId]);

  /* ── Reconcile data ── */
  const reconcile = useCallback(() => {
    const s = sim.current;
    const oldMap = s.nodeMap;
    const newNodeMap = new Map<string, SimNode>();
    const now = performance.now();

    // Cluster centers for initial positioning
    const cx = s.width / 2;
    const cy = s.height / 2;
    const cr = Math.min(s.width, s.height) * CLUSTER_RADIUS_RATIO;

    for (const n of nodes) {
      const existing = oldMap.get(n.id);
      if (existing) {
        // Update content fields, keep physics state
        existing.content = n.content;
        existing.clusterIndex = n.clusterIndex;
        existing.clusterLabel = n.clusterLabel;
        existing.connectionCount = n.connectionCount;
        existing.createdAt = n.createdAt;
        newNodeMap.set(n.id, existing);
      } else {
        // New node — place near cluster center with some jitter
        const angle = s.rotation + n.clusterIndex * (2 * Math.PI / 3);
        const targetX = cx + cr * Math.cos(angle);
        const targetY = cy + cr * Math.sin(angle);
        const sn: SimNode = {
          id: n.id,
          content: n.content,
          clusterIndex: n.clusterIndex,
          clusterLabel: n.clusterLabel,
          connectionCount: n.connectionCount,
          createdAt: n.createdAt,
          x: targetX + (Math.random() - 0.5) * 60,
          y: targetY + (Math.random() - 0.5) * 60,
          vx: 0,
          vy: 0,
          expand: 0,
          targetExpand: 0,
          jitterPhase: Math.random() * Math.PI * 2,
          jitterSpeed: 0.8 + Math.random() * 1.2,
          birthTime: now,
          birthDone: s.prevNodeIds.has(n.id), // only animate truly new nodes
        };
        newNodeMap.set(n.id, sn);
      }
    }

    // Build adjacency
    const adjacency = new Map<string, Set<string>>();
    for (const n of nodes) {
      adjacency.set(n.id, new Set());
    }
    for (const e of edges) {
      adjacency.get(e.source)?.add(e.target);
      adjacency.get(e.target)?.add(e.source);
    }

    // Build sim edges
    const simEdges: SimEdge[] = edges.map((e) => {
      const sn = newNodeMap.get(e.source);
      const tn = newNodeMap.get(e.target);
      const isCross = sn && tn ? sn.clusterIndex !== tn.clusterIndex : false;
      // Check if this is a new edge
      const wasConnected = s.adjacency.get(e.source)?.has(e.target);
      return {
        sourceId: e.source,
        targetId: e.target,
        weight: e.weight,
        isCross,
        particleOffset: Math.random(),
        stitchProgress: wasConnected ? 1 : 0,
      };
    });

    s.nodes = Array.from(newNodeMap.values());
    s.edges = simEdges;
    s.nodeMap = newNodeMap;
    s.adjacency = adjacency;
    s.prevNodeIds = new Set(nodes.map((n) => n.id));
  }, [nodes, edges]);

  useEffect(() => {
    reconcile();
  }, [reconcile]);

  /* ── Resize ── */
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const handleResize = () => {
      const dpr = window.devicePixelRatio || 1;
      const rect = canvas.getBoundingClientRect();
      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;
      sim.current.width = rect.width;
      sim.current.height = rect.height;
      sim.current.dpr = dpr;
    };

    handleResize();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  /* ── Mouse / touch ── */
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const getPos = (e: MouseEvent | Touch) => {
      const rect = canvas.getBoundingClientRect();
      return { x: e.clientX - rect.left, y: e.clientY - rect.top };
    };

    const findNode = (x: number, y: number): SimNode | null => {
      const s = sim.current;
      let closest: SimNode | null = null;
      let closestDist = 24; // hit radius
      for (const n of s.nodes) {
        const jx = n.x + Math.sin(s.time * n.jitterSpeed + n.jitterPhase) * 1.2;
        const jy = n.y + Math.cos(s.time * n.jitterSpeed * 1.3 + n.jitterPhase) * 1.2;
        const d = dist(x, y, jx, jy);
        if (d < closestDist) {
          closestDist = d;
          closest = n;
        }
      }
      return closest;
    };

    const handleMove = (e: MouseEvent) => {
      const pos = getPos(e);
      sim.current.mouseX = pos.x;
      sim.current.mouseY = pos.y;
      const node = findNode(pos.x, pos.y);
      const prevId = sim.current.hoveredId;
      sim.current.hoveredId = node?.id ?? null;
      if (node?.id !== prevId) {
        const cn = node ? nodes.find((n) => n.id === node.id) ?? null : null;
        onHoverNode(cn);
      }
    };

    const handleClick = (e: MouseEvent) => {
      const pos = getPos(e);
      const node = findNode(pos.x, pos.y);
      const s = sim.current;

      if (node) {
        if (s.selectedId === node.id) {
          // Deselect
          s.selectedId = null;
          onSelectNode(null);
        } else {
          s.selectedId = node.id;
          const cn = nodes.find((n) => n.id === node.id) ?? null;
          onSelectNode(cn);
        }
      } else {
        if (s.selectedId) {
          s.selectedId = null;
          onSelectNode(null);
        }
      }
    };

    const handleLeave = () => {
      sim.current.mouseX = -9999;
      sim.current.mouseY = -9999;
      if (sim.current.hoveredId) {
        sim.current.hoveredId = null;
        onHoverNode(null);
      }
    };

    // Touch support
    const handleTouchStart = (e: TouchEvent) => {
      if (e.touches.length === 1) {
        const pos = getPos(e.touches[0]);
        const node = findNode(pos.x, pos.y);
        const s = sim.current;
        if (node) {
          e.preventDefault();
          if (s.selectedId === node.id) {
            s.selectedId = null;
            onSelectNode(null);
          } else {
            s.selectedId = node.id;
            const cn = nodes.find((n) => n.id === node.id) ?? null;
            onSelectNode(cn);
          }
        } else if (s.selectedId) {
          s.selectedId = null;
          onSelectNode(null);
        }
      }
    };

    canvas.addEventListener("mousemove", handleMove);
    canvas.addEventListener("click", handleClick);
    canvas.addEventListener("mouseleave", handleLeave);
    canvas.addEventListener("touchstart", handleTouchStart, { passive: false });

    return () => {
      canvas.removeEventListener("mousemove", handleMove);
      canvas.removeEventListener("click", handleClick);
      canvas.removeEventListener("mouseleave", handleLeave);
      canvas.removeEventListener("touchstart", handleTouchStart);
    };
  }, [nodes, onSelectNode, onHoverNode]);

  /* ── Animation loop ── */
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let running = true;

    const tick = () => {
      const s = sim.current;
      if (s.nodes.length === 0) return;

      s.time += 0.016; // ~60fps time step
      s.rotation += GLOBAL_ROTATION_SPEED;

      const cx = s.width / 2;
      const cy = s.height / 2;
      const cr = Math.min(s.width, s.height) * CLUSTER_RADIUS_RATIO;

      // Cluster center positions (rotating triangle)
      const clusterCenters: [number, number][] = [0, 1, 2].map((i) => {
        const a = s.rotation + i * (2 * Math.PI / 3);
        return [cx + cr * Math.cos(a), cy + cr * Math.sin(a)];
      });

      // Scale node count
      const nodeCount = s.nodes.length;
      const densityScale = nodeCount > 30 ? Math.max(0.6, 30 / nodeCount) : 1;

      // Forces
      for (const n of s.nodes) {
        // Cluster gravity
        const cc = clusterCenters[n.clusterIndex % 3];
        const dx = cc[0] - n.x;
        const dy = cc[1] - n.y;
        n.vx += dx * CLUSTER_GRAVITY;
        n.vy += dy * CLUSTER_GRAVITY;
      }

      // Repulsion (O(n²) fine for <100 nodes)
      for (let i = 0; i < s.nodes.length; i++) {
        for (let j = i + 1; j < s.nodes.length; j++) {
          const a = s.nodes[i];
          const b = s.nodes[j];
          const dx = b.x - a.x;
          const dy = b.y - a.y;
          const d2 = dx * dx + dy * dy + 1;
          const d = Math.sqrt(d2);
          const force = (REPULSION * densityScale) / d2;
          const fx = (dx / d) * force;
          const fy = (dy / d) * force;
          a.vx -= fx;
          a.vy -= fy;
          b.vx += fx;
          b.vy += fy;
        }
      }

      // Edge springs
      for (const e of s.edges) {
        const a = s.nodeMap.get(e.sourceId);
        const b = s.nodeMap.get(e.targetId);
        if (!a || !b) continue;
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const d = Math.sqrt(dx * dx + dy * dy) + 0.1;
        const restLen = EDGE_REST * densityScale;
        const displacement = d - restLen;
        const fx = (dx / d) * displacement * EDGE_SPRING;
        const fy = (dy / d) * displacement * EDGE_SPRING;
        a.vx += fx;
        a.vy += fy;
        b.vx -= fx;
        b.vy -= fy;
      }

      // Integrate + damp
      const margin = 40;
      for (const n of s.nodes) {
        n.vx *= DAMPING;
        n.vy *= DAMPING;
        n.x += n.vx;
        n.y += n.vy;
        // Soft boundary
        if (n.x < margin) n.vx += (margin - n.x) * 0.05;
        if (n.x > s.width - margin) n.vx += (s.width - margin - n.x) * 0.05;
        if (n.y < margin) n.vy += (margin - n.y) * 0.05;
        if (n.y > s.height - margin) n.vy += (s.height - margin - n.y) * 0.05;
      }

      // Update expand targets
      const hovered = s.hoveredId ? s.nodeMap.get(s.hoveredId) : null;
      const selected = s.selectedId ? s.nodeMap.get(s.selectedId) : null;
      const hoveredNeighbors = s.hoveredId ? s.adjacency.get(s.hoveredId) : null;
      const selectedNeighbors = s.selectedId ? s.adjacency.get(s.selectedId) : null;

      for (const n of s.nodes) {
        if (n.id === s.selectedId || n.id === s.hoveredId) {
          n.targetExpand = 1;
        } else if (
          (hoveredNeighbors && hoveredNeighbors.has(n.id)) ||
          (selectedNeighbors && selectedNeighbors.has(n.id))
        ) {
          n.targetExpand = 0.5;
        } else if (hovered || selected) {
          n.targetExpand = -0.2; // dim further
        } else {
          n.targetExpand = 0;
        }
        // Smooth interpolation
        n.expand = lerp(n.expand, n.targetExpand, 0.1);
      }

      // Birth animation progress
      const now = performance.now();
      for (const n of s.nodes) {
        if (!n.birthDone) {
          const elapsed = now - n.birthTime;
          if (elapsed > 1200) {
            n.birthDone = true;
          }
        }
      }

      // Edge stitch progress
      for (const e of s.edges) {
        if (e.stitchProgress < 1) {
          e.stitchProgress = Math.min(1, e.stitchProgress + 0.015);
        }
      }

      // Particle offsets
      for (const e of s.edges) {
        e.particleOffset = (e.particleOffset + PARTICLE_SPEED) % 1;
      }

      // Phantom connections
      if (now - s.lastPhantomTime > PHANTOM_INTERVAL && s.nodes.length > 3) {
        s.lastPhantomTime = now;
        const a = s.nodes[Math.floor(Math.random() * s.nodes.length)];
        const b = s.nodes[Math.floor(Math.random() * s.nodes.length)];
        if (a.id !== b.id && !s.adjacency.get(a.id)?.has(b.id)) {
          s.phantoms.push({
            x1: a.x, y1: a.y,
            x2: b.x, y2: b.y,
            life: 0, maxLife: 80 + Math.random() * 60,
          });
        }
      }
      s.phantoms = s.phantoms.filter((p) => {
        p.life += 1;
        return p.life < p.maxLife;
      });

      // Signal flickers
      if (now - s.lastFlickerTime > FLICKER_INTERVAL && s.nodes.length > 2) {
        s.lastFlickerTime = now;
        const a = s.nodes[Math.floor(Math.random() * s.nodes.length)];
        const b = s.nodes[Math.floor(Math.random() * s.nodes.length)];
        if (a.id !== b.id) {
          const t = Math.random();
          s.flickers.push({
            x: lerp(a.x, b.x, t),
            y: lerp(a.y, b.y, t),
            life: 0,
            maxLife: 30 + Math.random() * 20,
          });
        }
      }
      s.flickers = s.flickers.filter((f) => {
        f.life += 1;
        return f.life < f.maxLife;
      });
    };

    const render = () => {
      const s = sim.current;
      const dpr = s.dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

      // Clear
      ctx.fillStyle = BG_COLOR;
      ctx.fillRect(0, 0, s.width, s.height);

      if (s.nodes.length === 0) return;

      const hovered = s.hoveredId ? s.nodeMap.get(s.hoveredId) : null;
      const selected = s.selectedId ? s.nodeMap.get(s.selectedId) : null;
      const activeNode = hovered || selected;

      // ── Signal flickers ──
      for (const f of s.flickers) {
        const t = f.life / f.maxLife;
        const alpha = t < 0.3 ? t / 0.3 : (1 - t) / 0.7;
        ctx.beginPath();
        ctx.arc(f.x, f.y, 1.2, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(26,26,26,${alpha * 0.08})`;
        ctx.fill();
      }

      // ── Phantom connections ──
      for (const p of s.phantoms) {
        const t = p.life / p.maxLife;
        const alpha = t < 0.2 ? t / 0.2 : t > 0.7 ? (1 - t) / 0.3 : 1;
        ctx.beginPath();
        ctx.moveTo(p.x1, p.y1);
        ctx.lineTo(p.x2, p.y2);
        ctx.strokeStyle = `rgba(26,26,26,${alpha * 0.04})`;
        ctx.lineWidth = 0.5;
        ctx.setLineDash([2, 12]);
        ctx.stroke();
        ctx.setLineDash([]);
      }

      // ── Connections ──
      for (const e of s.edges) {
        const a = s.nodeMap.get(e.sourceId);
        const b = s.nodeMap.get(e.targetId);
        if (!a || !b) continue;

        const jax = a.x + Math.sin(s.time * a.jitterSpeed + a.jitterPhase) * 1.2;
        const jay = a.y + Math.cos(s.time * a.jitterSpeed * 1.3 + a.jitterPhase) * 1.2;
        const jbx = b.x + Math.sin(s.time * b.jitterSpeed + b.jitterPhase) * 1.2;
        const jby = b.y + Math.cos(s.time * b.jitterSpeed * 1.3 + b.jitterPhase) * 1.2;

        const isActive =
          activeNode &&
          (a.id === activeNode.id || b.id === activeNode.id);

        // Stitch animation — only draw portion of line
        const stitch = e.stitchProgress;
        const midX = lerp(jax, jbx, stitch);
        const midY = lerp(jay, jby, stitch);

        if (isActive) {
          // Active: continuous dashes with cluster color
          const color = e.isCross
            ? lerpColor(
                CLUSTER_COLORS[a.clusterIndex % 3],
                CLUSTER_COLORS[b.clusterIndex % 3],
                0.5
              )
            : CLUSTER_COLORS[a.clusterIndex % 3];

          ctx.beginPath();
          ctx.moveTo(jax, jay);
          ctx.lineTo(midX, midY);
          ctx.strokeStyle = rgba(color, 0.35);
          ctx.lineWidth = 1;
          ctx.setLineDash([6, 4]);
          ctx.lineDashOffset = -s.time * 30;
          ctx.stroke();
          ctx.setLineDash([]);
          ctx.lineDashOffset = 0;

          // Signal particles
          const d = dist(jax, jay, jbx, jby);
          const particleCount = Math.max(2, Math.floor(d / 60));
          for (let i = 0; i < particleCount; i++) {
            const t = ((e.particleOffset + i / particleCount) % 1) * stitch;
            const px = lerp(jax, jbx, t);
            const py = lerp(jay, jby, t);
            ctx.beginPath();
            ctx.arc(px, py, PARTICLE_RADIUS, 0, Math.PI * 2);
            ctx.fillStyle = rgba(color, 0.5);
            ctx.fill();
          }
        } else {
          // Default: faint fragmented dashes
          const dimFactor = activeNode ? 0.03 : 0.07;
          ctx.beginPath();
          ctx.moveTo(jax, jay);
          ctx.lineTo(midX, midY);
          ctx.strokeStyle = `rgba(26,26,26,${dimFactor})`;
          ctx.lineWidth = 0.5;
          ctx.setLineDash([2, 10]);
          ctx.stroke();
          ctx.setLineDash([]);
        }
      }

      // ── Cluster labels ──
      const cx = s.width / 2;
      const cy = s.height / 2;
      const cr = Math.min(s.width, s.height) * CLUSTER_RADIUS_RATIO;
      const clusterLabels = ["Technology", "Growth", "Purpose"];

      // Compute actual cluster centers from node positions
      for (let ci = 0; ci < 3; ci++) {
        const clusterNodes = s.nodes.filter((n) => n.clusterIndex % 3 === ci);
        if (clusterNodes.length === 0) continue;

        let avgX = 0, avgY = 0;
        for (const n of clusterNodes) {
          avgX += n.x;
          avgY += n.y;
        }
        avgX /= clusterNodes.length;
        avgY /= clusterNodes.length;

        // Use first node's clusterLabel or default
        const label = clusterNodes[0].clusterLabel || clusterLabels[ci];

        ctx.font = "300 11px 'Sora', sans-serif";
        ctx.fillStyle = rgba(CLUSTER_COLORS[ci], 0.14);
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(label.toLowerCase(), avgX, avgY - 28);
      }

      // ── Nodes ──
      // Sort: selected/hovered on top
      const sortedNodes = [...s.nodes].sort((a, b) => {
        const aWeight = a.id === s.selectedId ? 2 : a.id === s.hoveredId ? 1 : 0;
        const bWeight = b.id === s.selectedId ? 2 : b.id === s.hoveredId ? 1 : 0;
        return aWeight - bWeight;
      });

      const now = performance.now();

      for (const n of sortedNodes) {
        const color = CLUSTER_COLORS[n.clusterIndex % 3];
        const jx = n.x + Math.sin(s.time * n.jitterSpeed + n.jitterPhase) * 1.2;
        const jy = n.y + Math.cos(s.time * n.jitterSpeed * 1.3 + n.jitterPhase) * 1.2;

        const expandClamped = Math.max(0, n.expand);

        // Birth animation (expanding rings from center)
        let birthScale = 1;
        let birthRings = 0;
        if (!n.birthDone) {
          const elapsed = now - n.birthTime;
          birthScale = Math.min(1, elapsed / 600);
          birthRings = Math.min(1, elapsed / 1200);

          // Boot-up expanding rings
          const ringCount = 3;
          for (let i = 0; i < ringCount; i++) {
            const ringProgress = Math.max(0, Math.min(1, (elapsed - i * 150) / 800));
            const ringRadius = ringProgress * (20 + i * 12);
            const ringAlpha = (1 - ringProgress) * 0.2;
            if (ringAlpha > 0.01) {
              ctx.beginPath();
              ctx.arc(jx, jy, ringRadius, 0, Math.PI * 2);
              ctx.strokeStyle = rgba(color, ringAlpha);
              ctx.lineWidth = 1;
              ctx.stroke();
            }
          }
        }

        // Dim factor when something is active but this node is unrelated
        const dimAmount = activeNode && expandClamped <= 0 ? 0.3 : 1;

        if (expandClamped > 0.05) {
          // ── Expanded / partially expanded state ──
          // Concentric rings (radar ping effect)
          for (let i = 0; i < RING_COUNT; i++) {
            const ringR = (DORMANT_RING + i * RING_SPACING * expandClamped) * birthScale;
            const ringAlpha = (1 - i / RING_COUNT) * expandClamped * 0.35;
            ctx.beginPath();
            ctx.arc(jx, jy, ringR, 0, Math.PI * 2);
            ctx.strokeStyle = rgba(color, ringAlpha);
            ctx.lineWidth = 1;
            ctx.stroke();
          }

          // Center fill with color
          const r = lerp(DORMANT_RADIUS, EXPANDED_RADIUS, expandClamped) * birthScale;
          ctx.beginPath();
          ctx.arc(jx, jy, r, 0, Math.PI * 2);
          ctx.fillStyle = rgba(color, 0.15 + expandClamped * 0.5);
          ctx.fill();

          // Core dot
          ctx.beginPath();
          ctx.arc(jx, jy, DORMANT_RADIUS * birthScale, 0, Math.PI * 2);
          ctx.fillStyle = rgba(color, 0.7 + expandClamped * 0.3);
          ctx.fill();
        } else {
          // ── Dormant state ──
          // Dark point
          ctx.beginPath();
          ctx.arc(jx, jy, DORMANT_RADIUS * birthScale, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(42,42,42,${0.6 * dimAmount})`;
          ctx.fill();

          // Subtle 1px ring
          ctx.beginPath();
          ctx.arc(jx, jy, DORMANT_RING * birthScale, 0, Math.PI * 2);
          ctx.strokeStyle = `rgba(42,42,42,${0.18 * dimAmount})`;
          ctx.lineWidth = 1;
          ctx.stroke();
        }
      }
    };

    const loop = () => {
      if (!running) return;
      tick();
      render();
      sim.current.frameId = requestAnimationFrame(loop);
    };

    sim.current.frameId = requestAnimationFrame(loop);

    return () => {
      running = false;
      cancelAnimationFrame(sim.current.frameId);
    };
  }, []); // Intentionally empty — reads from sim.current

  return <canvas ref={canvasRef} />;
});
