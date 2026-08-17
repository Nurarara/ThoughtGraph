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

const BG = "#020a11";
const EDGE = "rgba(63, 198, 220, 0.13)";
const EDGE_ACTIVE = "rgba(244, 174, 66, 0.72)";
const TEXT = "rgba(242, 247, 246, 0.96)";
const MUTED = "rgba(196, 218, 225, 0.66)";

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
    node.kind === "image" ? 12 : node.kind === "video" ? 13 : node.kind === "link" ? 10 : 9;
  const connected = clamp(Math.sqrt(Math.max(0, node.connection_count)) * 1.8, 0, 8);
  const zoomBoost = clamp((zoom - 0.7) * 1.5, 0, 4);
  return isActive ? base + 5 + connected * 0.7 + zoomBoost : base + connected * 0.52;
}

function strokeFor(edge: GraphEdgeRecord, active: boolean) {
  if (active) {
    return EDGE_ACTIVE;
  }
  return edge.weight > 0.75 ? "rgba(63, 198, 220, 0.3)" : EDGE;
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
  const inertiaFrameRef = useRef<number | null>(null);
  const viewportRef = useRef(viewport);
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [size, setSize] = useState({ width: 0, height: 0, dpr: 1 });
  const pointerState = useRef<{
    pointerId: number;
    startX: number;
    startY: number;
    lastX: number;
    lastY: number;
    lastMoveAt: number;
    velocityX: number;
    velocityY: number;
    downNodeId: string | null;
    dragging: boolean;
  } | null>(null);

  const nodesById = useMemo(() => new Map(graph?.nodes.map((node) => [node.id, node]) ?? []), [graph]);

  useEffect(() => {
    viewportRef.current = viewport;
  }, [viewport]);

  useEffect(() => () => {
    if (inertiaFrameRef.current !== null) window.cancelAnimationFrame(inertiaFrameRef.current);
  }, []);

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
    const activeNeighborIds = new Set(
      activeNodeId
        ? graph.edges
            .filter((edge) => edge.source === activeNodeId || edge.target === activeNodeId)
            .sort((left, right) => right.weight - left.weight)
            .slice(0, size.width < 700 ? 0 : 2)
            .map((edge) => edge.source === activeNodeId ? edge.target : edge.source)
        : [],
    );
    const zoom = viewport.zoom_hint;

    const gradient = ctx.createRadialGradient(
      size.width * 0.58,
      size.height * 0.48,
      24,
      size.width * 0.58,
      size.height * 0.48,
      Math.max(size.width, size.height) * 0.7,
    );
    gradient.addColorStop(0, "#071a24");
    gradient.addColorStop(1, BG);
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, size.width, size.height);

    ctx.strokeStyle = "rgba(118, 189, 202, 0.035)";
    ctx.lineWidth = 1;
    for (let x = 0; x <= size.width; x += 80) {
      ctx.beginPath();
      ctx.moveTo(x + 0.5, 0);
      ctx.lineTo(x + 0.5, size.height);
      ctx.stroke();
    }
    for (let y = 0; y <= size.height; y += 80) {
      ctx.beginPath();
      ctx.moveTo(0, y + 0.5);
      ctx.lineTo(size.width, y + 0.5);
      ctx.stroke();
    }

    const clusterGroups = new Map<string, GraphNodeRecord[]>();
    for (const node of graph.nodes) {
      const key = node.cluster_label ?? "unknown";
      const bucket = clusterGroups.get(key) ?? [];
      bucket.push(node);
      clusterGroups.set(key, bucket);
    }
    const representativeNodeIds = new Set(
      [...clusterGroups.values()].flatMap((items) =>
        [...items]
          .sort((left, right) => right.connection_count - left.connection_count || left.id.localeCompare(right.id))
          .slice(0, 2)
          .map((node) => node.id),
      ),
    );

    const clusterLabelPoints = new Map<string, { x: number; y: number }>();
    for (const [label, items] of clusterGroups) {
      if (items.length < 2) continue;
      const points = items.map((node) => toScreen(node, viewport, size.width, size.height));
      const centroid = points.reduce((acc, point) => ({ x: acc.x + point.x, y: acc.y + point.y }), { x: 0, y: 0 });
      centroid.x /= points.length;
      centroid.y /= points.length;
      const fieldRadius = Math.max(42, ...points.map((point) => Math.hypot(point.x - centroid.x, point.y - centroid.y))) + 28;
      clusterLabelPoints.set(label, {
        x: centroid.x,
        y: centroid.y - fieldRadius * 0.72 - 14,
      });
      ctx.save();
      ctx.strokeStyle = items[0].cluster_color ?? "#3fc6dc";
      ctx.globalAlpha = 0.11;
      ctx.lineWidth = 1;
      for (const scale of [0.62, 0.82, 1]) {
        ctx.beginPath();
        ctx.ellipse(centroid.x, centroid.y, fieldRadius * scale, fieldRadius * 0.72 * scale, -0.12, 0, Math.PI * 2);
        ctx.stroke();
      }
      ctx.restore();
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

    for (const [label, items] of clusterGroups) {
      if (items.length < 2) {
        continue;
      }
      const point = clusterLabelPoints.get(label);
      if (!point) continue;
      ctx.fillStyle = items[0].cluster_color ?? "rgba(63, 198, 220, 0.8)";
      ctx.globalAlpha = 0.78;
      ctx.font = "500 11px 'IBM Plex Mono', monospace";
      ctx.textAlign = "center";
      ctx.fillText(label.toUpperCase(), point.x, point.y);
      ctx.globalAlpha = 1;
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

      const nodeFill = ctx.createRadialGradient(
        point.x - radius * 0.3,
        point.y - radius * 0.32,
        Math.max(1, radius * 0.08),
        point.x,
        point.y,
        radius,
      );
      nodeFill.addColorStop(0, fill);
      nodeFill.addColorStop(0.48, fill);
      nodeFill.addColorStop(1, "rgba(2, 10, 17, 0.96)");
      ctx.beginPath();
      ctx.arc(point.x, point.y, radius, 0, Math.PI * 2);
      ctx.fillStyle = nodeFill;
      ctx.globalAlpha = alpha;
      ctx.fill();
      ctx.globalAlpha = 1;
      ctx.strokeStyle = fill;
      ctx.globalAlpha = isActive ? 0.92 : 0.6;
      ctx.stroke();
      ctx.globalAlpha = 1;

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

      const showLabel = isActive
        || (size.width >= 700 && (activeNodeId ? activeNeighborIds.has(node.id) : representativeNodeIds.has(node.id)))
        || (size.width >= 700 && zoom > 2.4);
      if (showLabel) {
        const persistentFocus = isSelected || isFocused;
        const label = persistentFocus ? "FOCUSED NODE" : nodeDisplayLabel(node, isActive ? 30 : 22);
        ctx.font = persistentFocus
          ? "500 10px 'IBM Plex Mono', monospace"
          : isActive
            ? "600 13px 'IBM Plex Sans', sans-serif"
            : "500 11px 'IBM Plex Sans', sans-serif";
        ctx.textAlign = "left";
        ctx.textBaseline = "middle";
        const x = point.x + radius + 10;
        const y = point.y - 1;
        ctx.shadowColor = "rgba(2, 10, 17, 0.96)";
        ctx.shadowBlur = 7;
        ctx.fillStyle = persistentFocus ? "rgba(244, 174, 66, 0.94)" : isActive ? TEXT : MUTED;
        ctx.fillText(label, x, y);
        if (node.author_display_name && isActive) {
          ctx.font = "400 9px 'IBM Plex Mono', monospace";
          ctx.fillStyle = node.is_social ? "rgba(63, 198, 220, 0.84)" : "rgba(196, 218, 225, 0.62)";
          ctx.fillText(`@${node.author_display_name}`, x, y + 12);
        }
        ctx.shadowBlur = 0;
      }
    }

    if (activeNodePosition && activeNode) {
      ctx.strokeStyle = "rgba(63, 198, 220, 0.86)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      const focusRadius = nodeRadius(activeNode, true, zoom) + 20;
      ctx.arc(activeNodePosition.x, activeNodePosition.y, focusRadius, 0, Math.PI * 2);
      ctx.stroke();
      for (const angle of [0, Math.PI / 2, Math.PI, Math.PI * 1.5]) {
        ctx.beginPath();
        ctx.moveTo(
          activeNodePosition.x + Math.cos(angle) * (focusRadius + 6),
          activeNodePosition.y + Math.sin(angle) * (focusRadius + 6),
        );
        ctx.lineTo(
          activeNodePosition.x + Math.cos(angle) * (focusRadius + 22),
          activeNodePosition.y + Math.sin(angle) * (focusRadius + 22),
        );
        ctx.stroke();
      }
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

  const stopInertia = () => {
    if (inertiaFrameRef.current !== null) {
      window.cancelAnimationFrame(inertiaFrameRef.current);
      inertiaFrameRef.current = null;
    }
  };

  const startInertia = (initialVelocityX: number, initialVelocityY: number) => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    stopInertia();
    let velocityX = initialVelocityX;
    let velocityY = initialVelocityY;
    let lastTime = performance.now();
    const step = (time: number) => {
      const elapsed = Math.min(32, Math.max(1, time - lastTime));
      lastTime = time;
      const current = viewportRef.current;
      const next = {
        ...current,
        center_x: current.center_x - (velocityX * elapsed) / current.zoom_hint,
        center_y: current.center_y - (velocityY * elapsed) / current.zoom_hint,
      };
      viewportRef.current = next;
      onViewportChange(next);
      const friction = Math.pow(0.88, elapsed / 16.67);
      velocityX *= friction;
      velocityY *= friction;
      if (Math.hypot(velocityX, velocityY) < 0.008) {
        inertiaFrameRef.current = null;
        return;
      }
      inertiaFrameRef.current = window.requestAnimationFrame(step);
    };
    inertiaFrameRef.current = window.requestAnimationFrame(step);
  };

  const handlePointerDown = (event: ReactPointerEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas || !graph) {
      return;
    }
    stopInertia();
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
      lastMoveAt: performance.now(),
      velocityX: 0,
      velocityY: 0,
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
      const now = performance.now();
      const elapsed = Math.max(1, now - active.lastMoveAt);
      active.velocityX = active.velocityX * 0.58 + (deltaX / elapsed) * 0.42;
      active.velocityY = active.velocityY * 0.58 + (deltaY / elapsed) * 0.42;
      active.lastMoveAt = now;
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

    if (active.dragging) startInertia(active.velocityX, active.velocityY);
    pointerState.current = null;
  };

  const handlePointerLeave = () => {
    setHoveredNodeId(null);
  };

  const handleWheel = (event: React.WheelEvent<HTMLCanvasElement>) => {
    if (!graph || size.width === 0 || size.height === 0) {
      return;
    }
    stopInertia();
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
