import { useEffect, useMemo, useRef, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";
import ForceGraph3D from "react-force-graph-3d";

import type { GraphNode, GraphResponse } from "../types";

interface NeuralGalaxyProps {
  graph: GraphResponse | null;
  timelinePoint: number | null;
  activeClusterId: string | null;
  hoveredNode: GraphNode | null;
  onHoverNode: (node: GraphNode | null) => void;
  onSelectNode: (node: GraphNode | null) => void;
}

type RenderNode = GraphNode & { opacity: number };
type RenderLink = GraphResponse["edges"][number] & { opacity: number };

function hexToRgba(hex: string, alpha: number) {
  const normalized = hex.replace("#", "");
  const r = Number.parseInt(normalized.slice(0, 2), 16);
  const g = Number.parseInt(normalized.slice(2, 4), 16);
  const b = Number.parseInt(normalized.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function useIsMobile() {
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);
  useEffect(() => {
    const listener = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener("resize", listener);
    return () => window.removeEventListener("resize", listener);
  }, []);
  return isMobile;
}

export function NeuralGalaxy({
  graph,
  timelinePoint,
  activeClusterId,
  hoveredNode,
  onHoverNode,
  onSelectNode,
}: NeuralGalaxyProps) {
  const isMobile = useIsMobile();
  const graphRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [pointer, setPointer] = useState({ x: 0, y: 0 });

  useEffect(() => {
    const element = containerRef.current;
    if (!element) {
      return;
    }
    const handleMove = (event: MouseEvent) => {
      const bounds = element.getBoundingClientRect();
      setPointer({ x: event.clientX - bounds.left, y: event.clientY - bounds.top });
    };
    element.addEventListener("mousemove", handleMove);
    return () => element.removeEventListener("mousemove", handleMove);
  }, []);

  const renderData = useMemo(() => {
    if (!graph) {
      return { nodes: [], links: [] as RenderLink[] };
    }

    const latest = timelinePoint ?? (graph.last_thought_at ? new Date(graph.last_thought_at).getTime() : Date.now());
    const start = latest - 30 * 24 * 60 * 60 * 1000;

    const nodes: RenderNode[] = [...graph.nodes, ...(graph.social_nodes ?? [])].map((node) => {
      const createdAt = new Date(node.created_at).getTime();
      const insideWindow = createdAt >= start && createdAt <= latest;
      const clusterVisible = !activeClusterId || node.cluster_id === activeClusterId || !!node.is_social;
      return {
        ...node,
        opacity: insideWindow && clusterVisible ? (node.is_social ? 0.76 : 0.95) : 0.08,
      };
    });

    const nodeMap = new Map(nodes.map((node) => [node.id, node]));
    const links: RenderLink[] = [...graph.edges, ...(graph.social_edges ?? [])].map((edge) => {
      const source = nodeMap.get(edge.source);
      const target = nodeMap.get(edge.target);
      const visible = (source?.opacity ?? 0) > 0.1 && (target?.opacity ?? 0) > 0.1;
      return {
        ...edge,
        opacity: visible ? (edge.kind === "cross_semantic_link" ? 0.42 : 0.32) : 0.02,
      };
    });

    return { nodes, links };
  }, [activeClusterId, graph, timelinePoint]);

  const sharedProps = {
    ref: graphRef,
    graphData: renderData,
    backgroundColor: "rgba(0,0,0,0)",
    linkColor: (link: RenderLink) => `rgba(232,230,240,${link.opacity})`,
    linkWidth: (link: RenderLink) => Math.max(0.4, link.weight * 3),
    linkDirectionalParticles: (link: RenderLink) =>
      hoveredNode && (link.source === hoveredNode.id || link.target === hoveredNode.id) ? 3 : 0,
    linkDirectionalParticleWidth: 2.5,
    nodeLabel: (node: RenderNode) => `${node.preview}`,
    onNodeHover: (node: RenderNode | null) => onHoverNode(node),
    onNodeClick: (node: RenderNode) => {
      onSelectNode(node);
      if (!isMobile) {
        graphRef.current?.cameraPosition?.(
          { x: (node as any).x ?? 0, y: (node as any).y ?? 0, z: ((node as any).z ?? 0) + 90 },
          node,
          800,
        );
      }
    },
  };

  return (
    <div className="graph-shell" ref={containerRef}>
      {graph && graph.nodes.length > 0 ? (
        isMobile ? (
          <ForceGraph2D
            {...sharedProps}
            cooldownTicks={90}
            nodeCanvasObject={(node: object, ctx: CanvasRenderingContext2D, globalScale: number) => {
              const renderNode = node as RenderNode;
              const label = renderNode.preview;
              const fontSize = 12 / globalScale;
              ctx.beginPath();
              ctx.fillStyle = `rgba(255,255,255,${renderNode.opacity * (renderNode.is_social ? 0.12 : 0.18)})`;
              ctx.arc((renderNode as any).x, (renderNode as any).y, renderNode.size * 1.9, 0, 2 * Math.PI);
              ctx.fill();
              ctx.beginPath();
              ctx.fillStyle = hexToRgba(renderNode.color, renderNode.opacity);
              ctx.arc((renderNode as any).x, (renderNode as any).y, renderNode.size, 0, 2 * Math.PI);
              ctx.fill();
              if (renderNode.is_social) {
                ctx.beginPath();
                ctx.strokeStyle = "rgba(255,255,255,0.55)";
                ctx.lineWidth = Math.max(1, 1.5 / globalScale);
                ctx.arc((renderNode as any).x, (renderNode as any).y, renderNode.size + 3, 0, 2 * Math.PI);
                ctx.stroke();
              }
              if (renderNode.opacity > 0.2 && renderNode.size > 10) {
                ctx.font = `${fontSize}px Outfit`;
                ctx.fillStyle = "rgba(232,230,240,0.8)";
                ctx.fillText(label.slice(0, 28), (renderNode as any).x + renderNode.size + 4, (renderNode as any).y + 4);
              }
            }}
            nodePointerAreaPaint={(node: object, color: string, ctx: CanvasRenderingContext2D) => {
              const renderNode = node as RenderNode;
              ctx.fillStyle = color;
              ctx.beginPath();
              ctx.arc((renderNode as any).x, (renderNode as any).y, renderNode.size + 8, 0, 2 * Math.PI);
              ctx.fill();
            }}
          />
        ) : (
          <ForceGraph3D
            {...sharedProps}
            nodeColor={(node: object) => hexToRgba((node as RenderNode).color, (node as RenderNode).opacity)}
            nodeVal={(node: object) => (node as RenderNode).size}
          />
        )
      ) : (
        <div className="graph-empty">
          <p>No thoughts yet.</p>
          <span>Your neural galaxy appears as soon as thoughts start colliding.</span>
        </div>
      )}

      {hoveredNode ? (
        <div className="graph-tooltip" style={{ left: pointer.x + 18, top: pointer.y + 18 }}>
          <p>{hoveredNode.preview}</p>
          <div className="tooltip-tags">
            {hoveredNode.topics.map((topic) => (
              <span key={topic}>{topic}</span>
            ))}
            <span>{hoveredNode.emotion}</span>
            {hoveredNode.author_display_name ? <span>{hoveredNode.author_display_name}</span> : null}
          </div>
          <small>{new Date(hoveredNode.created_at).toLocaleDateString()} - {hoveredNode.connection_count} connections</small>
        </div>
      ) : null}
    </div>
  );
}
