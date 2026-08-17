import { useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";

import type { GraphEdgeRecord, GraphNativeResponse, GraphNodeRecord, GraphViewport } from "../lib/apiClient";
import { nodeDisplayLabel } from "../lib/nodeDisplay";

interface GraphCanvasProps {
  graph: GraphNativeResponse | null;
  viewport: GraphViewport;
  selectedNodeId: string | null;
  focusedNodeId: string | null;
  onViewportChange: (viewport: GraphViewport) => void;
  onNodeSelect: (nodeId: string | null) => void;
  onNodeFocus: (nodeId: string | null) => void;
}

interface ScreenPoint {
  x: number;
  y: number;
}

const BG = "#0f1116";
const EDGE = "rgba(210, 220, 255, 0.1)";
const EDGE_ACTIVE = "rgba(220, 235, 255, 0.24)";
const TEXT = "rgba(246, 248, 255, 0.92)";
const MUTED = "rgba(246, 248, 255, 0.56)";

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function distance(a: ScreenPoint, b: ScreenPoint) {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

function toScreen(node: GraphNodeRecord, viewport: GraphViewport, width: number, height: number): ScreenPoint {
  return {
    x: (node.x - viewport.center_x) * viewport.zoom_hint + width / 2,
    y: (node.y - viewport.center_y) * viewport.zoom_hint + height / 2,
  };
}

function fromScreen(point: ScreenPoint, viewport: GraphViewport, width: number, height: number): ScreenPoint {
  return {
    x: (point.x - width / 2) / viewport.zoom_hint + viewport.center_x,
    y: (point.y - height / 2) / viewport.zoom_hint + viewport.center_y,
  };
}

function nodeRadius(node: GraphNodeRecord, isActive: boolean, zoom: number) {
  const base =
    node.kind === "image" ? 11 : node.kind === "video" ? 12 : node.kind === "link" ? 9 : 8;
  const connected = clamp(node.connection_count / 2, 0, 8);
  const zoomBoost = clamp((zoom - 0.7) * 1.8, 0, 4);
  return isActive ? base + 6 + connected * 0.4 + zoomBoost : base + connected * 0.25;
}

function strokeFor(edge: GraphEdgeRecord, active: boolean) {
  if (active) {
    return EDGE_ACTIVE;
  }
  return edge.weight > 0.75 ? "rgba(150, 190, 255, 0.2)" : EDGE;
}

export function GraphCanvas({
  graph,
  viewport,
  selectedNodeId,
  focusedNodeId,
  onViewportChange,
  onNodeSelect,
  onNodeFocus,
}: GraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [size, setSize] = useState({ width: 0, height: 0, dpr: 1 });
  const pointerState = useRef<{
    pointerId: number;
    startX: number;
    startY: number;
    lastX: number;
    lastY: number;
    downNodeId: string | null;
    dragging: boolean;
  } | null>(null);

  const nodesById = useMemo(() => new Map(graph?.nodes.map((node) => [node.id, node]) ?? []), [graph]);

  useEffect(() => {
    const element = containerRef.current;
    if (!element) {
      return;
    }

    const update = () => {
      const rect = element.getBoundingClientRect();
      setSize({
        width: rect.width,
        height: rect.height,
        dpr: window.devicePixelRatio || 1,
      });
    };

    update();

    const observer = new ResizeObserver(update);
    observer.observe(element);
    window.addEventListener("resize", update);
    return () => {
      observer.disconnect();
      window.removeEventListener("resize", update);
    };
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || size.width === 0 || size.height === 0) {
      return;
    }

    canvas.width = Math.floor(size.width * size.dpr);
    canvas.height = Math.floor(size.height * size.dpr);

    const ctx = canvas.getContext("2d");
    if (!ctx || !graph) {
      if (ctx) {
        ctx.setTransform(size.dpr, 0, 0, size.dpr, 0, 0);
        ctx.fillStyle = BG;
        ctx.fillRect(0, 0, size.width, size.height);
      }
      return;
    }

    ctx.setTransform(size.dpr, 0, 0, size.dpr, 0, 0);
    ctx.clearRect(0, 0, size.width, size.height);

    const activeNodeId = focusedNodeId ?? selectedNodeId ?? hoveredNodeId;
    const activeNode = activeNodeId ? nodesById.get(activeNodeId) ?? null : null;
    const activeNodePosition = activeNode ? toScreen(activeNode, viewport, size.width, size.height) : null;
    const zoom = viewport.zoom_hint;

    const gradient = ctx.createRadialGradient(
      size.width * 0.5,
      size.height * 0.45,
      24,
      size.width * 0.5,
      size.height * 0.5,
      Math.max(size.width, size.height) * 0.7,
    );
    gradient.addColorStop(0, "#171c27");
    gradient.addColorStop(1, BG);
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, size.width, size.height);

    ctx.strokeStyle = "rgba(255, 255, 255, 0.04)";
    ctx.lineWidth = 1;
    for (let x = 0; x <= size.width; x += 64) {
      ctx.beginPath();
      ctx.moveTo(x + 0.5, 0);
      ctx.lineTo(x + 0.5, size.height);
      ctx.stroke();
    }
    for (let y = 0; y <= size.height; y += 64) {
      ctx.beginPath();
      ctx.moveTo(0, y + 0.5);
      ctx.lineTo(size.width, y + 0.5);
      ctx.stroke();
    }

    for (const edge of graph.edges) {
      const source = nodesById.get(edge.source);
      const target = nodesById.get(edge.target);
      if (!source || !target) {
        continue;
      }

      const sourcePoint = toScreen(source, viewport, size.width, size.height);
      const targetPoint = toScreen(target, viewport, size.width, size.height);
      const edgeActive =
        activeNodeId !== null &&
        (source.id === activeNodeId || target.id === activeNodeId);

      ctx.beginPath();
      ctx.moveTo(sourcePoint.x, sourcePoint.y);
      if (sourcePoint.x === targetPoint.x && sourcePoint.y === targetPoint.y) {
        ctx.lineTo(targetPoint.x + 0.01, targetPoint.y + 0.01);
      } else {
        const midX = (sourcePoint.x + targetPoint.x) / 2;
        const midY = (sourcePoint.y + targetPoint.y) / 2;
        const bend = clamp(edge.weight, 0.1, 1) * 18;
        const dx = targetPoint.y - sourcePoint.y;
        const dy = sourcePoint.x - targetPoint.x;
        const length = Math.hypot(dx, dy) || 1;
        const offsetX = (dx / length) * bend;
        const offsetY = (dy / length) * bend;
        ctx.quadraticCurveTo(midX + offsetX, midY + offsetY, targetPoint.x, targetPoint.y);
      }
      ctx.strokeStyle = strokeFor(edge, edgeActive);
      ctx.lineWidth = edgeActive ? 2.4 : 1;
      ctx.stroke();
    }

    const clusterTitles = new Map<string, GraphNodeRecord[]>();
    for (const node of graph.nodes) {
      const bucket = clusterTitles.get(node.cluster_label ?? "unknown") ?? [];
      bucket.push(node);
      clusterTitles.set(node.cluster_label ?? "unknown", bucket);
    }

    for (const [label, items] of clusterTitles) {
      if (items.length < 2) {
        continue;
      }
      const centroid = items.reduce(
        (acc, node) => {
          acc.x += node.x;
          acc.y += node.y;
          return acc;
        },
        { x: 0, y: 0 },
      );
      const point = toScreen(
        {
          ...items[0],
          x: centroid.x / items.length,
          y: centroid.y / items.length,
        },
        viewport,
        size.width,
        size.height,
      );
      ctx.fillStyle = "rgba(255, 255, 255, 0.06)";
      ctx.font = "600 10px Inter, system-ui, sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(label.toUpperCase(), point.x, point.y - 18);
    }

    for (const node of graph.nodes) {
      const point = toScreen(node, viewport, size.width, size.height);
      const isSelected = node.id === selectedNodeId;
      const isFocused = node.id === focusedNodeId;
      const isHovered = node.id === hoveredNodeId;
      const isActive = isSelected || isFocused || isHovered;
      const radius = nodeRadius(node, isActive, zoom);
      const fill = node.cluster_color ?? "rgba(214, 217, 228, 0.85)";
      const socialRing = node.is_social ? "rgba(125, 255, 227, 0.34)" : "rgba(255, 255, 255, 0.09)";
      const mediaRing =
        node.kind === "video"
          ? "rgba(255, 179, 107, 0.32)"
          : node.kind === "image"
            ? "rgba(148, 182, 255, 0.28)"
            : socialRing;
      const alpha = isActive ? 1 : activeNodeId ? 0.42 : 0.82;

      ctx.beginPath();
      ctx.arc(point.x, point.y, radius + (isActive ? 4 : 2), 0, Math.PI * 2);
      ctx.fillStyle =
        node.kind === "image" || node.kind === "video"
          ? mediaRing
          : node.is_social
            ? socialRing
            : isActive
              ? "rgba(255, 255, 255, 0.09)"
              : "rgba(255, 255, 255, 0.03)";
      ctx.fill();

      ctx.beginPath();
      ctx.arc(point.x, point.y, radius, 0, Math.PI * 2);
      ctx.fillStyle = fill;
      ctx.globalAlpha = alpha;
      ctx.fill();
      ctx.globalAlpha = 1;

      ctx.beginPath();
      ctx.arc(point.x, point.y, Math.max(2, radius - 4), 0, Math.PI * 2);
      ctx.fillStyle = "rgba(10, 12, 18, 0.9)";
      ctx.fill();

      if (node.kind === "video") {
        ctx.beginPath();
        ctx.moveTo(point.x - 3, point.y - 5);
        ctx.lineTo(point.x + 6, point.y);
        ctx.lineTo(point.x - 3, point.y + 5);
        ctx.closePath();
        ctx.fillStyle = "rgba(255, 179, 107, 0.92)";
        ctx.fill();
      } else if (node.kind === "image") {
        const iconWidth = Math.max(7, radius - 5);
        const iconHeight = Math.max(5, radius - 7);
        ctx.strokeStyle = "rgba(148, 182, 255, 0.92)";
        ctx.lineWidth = 1.2;
        ctx.strokeRect(point.x - iconWidth / 2, point.y - iconHeight / 2, iconWidth, iconHeight);
        ctx.beginPath();
        ctx.moveTo(point.x - iconWidth / 2 + 1, point.y + iconHeight / 2 - 1);
        ctx.lineTo(point.x - 1, point.y - 1);
        ctx.lineTo(point.x + iconWidth / 2 - 1, point.y + iconHeight / 2 - 1);
        ctx.stroke();
        ctx.beginPath();
        ctx.arc(point.x + iconWidth / 4, point.y - iconHeight / 5, 1.4, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(148, 182, 255, 0.92)";
        ctx.fill();
      }

      if (isActive || zoom > 1.15) {
        const label = nodeDisplayLabel(node);
        ctx.font = isActive ? "600 13px Inter, system-ui, sans-serif" : "500 11px Inter, system-ui, sans-serif";
        ctx.textAlign = "left";
        ctx.textBaseline = "middle";
        const textWidth = Math.min(280, ctx.measureText(label).width + 24);
        const x = point.x + radius + 10;
        const y = point.y - 1;
        ctx.fillStyle = isActive ? TEXT : MUTED;
        ctx.fillText(label, x, y);
        if (node.author_display_name) {
          ctx.font = "500 9px Inter, system-ui, sans-serif";
          ctx.fillStyle = node.is_social ? "rgba(125, 255, 227, 0.82)" : "rgba(246, 248, 255, 0.6)";
          ctx.fillText(`@${node.author_display_name}`, x, y + 12);
        }
        if (isActive && node.preview_text) {
          ctx.font = "400 10px Inter, system-ui, sans-serif";
          ctx.fillStyle = "rgba(246, 248, 255, 0.7)";
          const preview = node.preview_text.slice(0, 80);
          ctx.fillText(preview, x, y + 24);
        }
        ctx.strokeStyle = node.is_social ? "rgba(125, 255, 227, 0.16)" : "rgba(255, 255, 255, 0.08)";
        ctx.strokeRect(x - 8, y - 16, textWidth, isActive ? 48 : 28);
      }
    }

    if (activeNodePosition && activeNode) {
      ctx.strokeStyle = activeNode.cluster_color ?? "rgba(255, 255, 255, 0.35)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(activeNodePosition.x, activeNodePosition.y, nodeRadius(activeNode, true, zoom) + 14, 0, Math.PI * 2);
      ctx.stroke();
    }
  }, [focusedNodeId, graph, hoveredNodeId, nodesById, selectedNodeId, size, viewport]);

  useEffect(() => {
    if (!graph) {
      setHoveredNodeId(null);
    }
  }, [graph]);

  const pickNode = (x: number, y: number) => {
    if (!graph || size.width === 0 || size.height === 0) {
      return null;
    }

    let nearest: GraphNodeRecord | null = null;
    let nearestDistance = Infinity;
    for (const node of graph.nodes) {
      const point = toScreen(node, viewport, size.width, size.height);
      const radius = nodeRadius(node, node.id === focusedNodeId || node.id === selectedNodeId, viewport.zoom_hint) + 10;
      const d = distance({ x, y }, point);
      if (d < radius && d < nearestDistance) {
        nearest = node;
        nearestDistance = d;
      }
    }
    return nearest;
  };

  const handlePointerDown = (event: ReactPointerEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas || !graph) {
      return;
    }
    canvas.setPointerCapture(event.pointerId);
    const rect = canvas.getBoundingClientRect();
    const localX = event.clientX - rect.left;
    const localY = event.clientY - rect.top;
    const hit = pickNode(localX, localY);
    pointerState.current = {
      pointerId: event.pointerId,
      startX: localX,
      startY: localY,
      lastX: localX,
      lastY: localY,
      downNodeId: hit?.id ?? null,
      dragging: false,
    };
  };

  const handlePointerMove = (event: ReactPointerEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    const active = pointerState.current;
    if (!canvas || !active || active.pointerId !== event.pointerId) {
      return;
    }

    const rect = canvas.getBoundingClientRect();
    const localX = event.clientX - rect.left;
    const localY = event.clientY - rect.top;
    const deltaX = localX - active.lastX;
    const deltaY = localY - active.lastY;
    const moved = Math.hypot(localX - active.startX, localY - active.startY);

    if (moved > 5) {
      active.dragging = true;
      onViewportChange({
        ...viewport,
        center_x: viewport.center_x - deltaX / viewport.zoom_hint,
        center_y: viewport.center_y - deltaY / viewport.zoom_hint,
      });
      active.lastX = localX;
      active.lastY = localY;
      setHoveredNodeId(pickNode(localX, localY)?.id ?? null);
      return;
    }

    setHoveredNodeId(pickNode(localX, localY)?.id ?? null);
  };

  const handlePointerUp = (event: ReactPointerEvent<HTMLCanvasElement>) => {
    const active = pointerState.current;
    if (!active || active.pointerId !== event.pointerId) {
      return;
    }

    const canvas = canvasRef.current;
    if (canvas?.hasPointerCapture(event.pointerId)) {
      canvas.releasePointerCapture(event.pointerId);
    }

    const rect = canvas?.getBoundingClientRect();
    if (rect) {
      const localX = event.clientX - rect.left;
      const localY = event.clientY - rect.top;
      const hit = pickNode(localX, localY);
      if (!active.dragging && hit) {
        onNodeSelect(hit.id);
        onNodeFocus(hit.id);
      } else if (!active.dragging && !hit) {
        onNodeSelect(null);
        onNodeFocus(null);
      }
    }

    pointerState.current = null;
  };

  const handlePointerLeave = () => {
    setHoveredNodeId(null);
  };

  const handleWheel = (event: React.WheelEvent<HTMLCanvasElement>) => {
    if (!graph || size.width === 0 || size.height === 0) {
      return;
    }
    event.preventDefault();
    const rect = event.currentTarget.getBoundingClientRect();
    const cursor = {
      x: event.clientX - rect.left,
      y: event.clientY - rect.top,
    };
    const worldBefore = fromScreen(cursor, viewport, size.width, size.height);
    const zoomFactor = Math.exp(-event.deltaY * 0.0012);
    const nextZoom = clamp(viewport.zoom_hint * zoomFactor, 0.45, 3.2);
    const worldAfter = {
      x: (cursor.x - size.width / 2) / nextZoom + viewport.center_x,
      y: (cursor.y - size.height / 2) / nextZoom + viewport.center_y,
    };

    onViewportChange({
      center_x: viewport.center_x + (worldBefore.x - worldAfter.x),
      center_y: viewport.center_y + (worldBefore.y - worldAfter.y),
      zoom_hint: nextZoom,
    });
  };

  return (
    <div className="graph-canvas-wrap" ref={containerRef}>
      <canvas
        ref={canvasRef}
        className="graph-canvas"
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
        onPointerLeave={handlePointerLeave}
        onWheel={handleWheel}
      />
      {!graph ? <div className="graph-canvas-empty">loading graph</div> : null}
    </div>
  );
}
