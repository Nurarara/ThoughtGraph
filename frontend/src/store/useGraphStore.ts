import { create } from "zustand";

import type { GraphNode } from "../types";

interface GraphState {
  selectedNode: GraphNode | null;
  hoveredNode: GraphNode | null;
  activeClusterId: string | null;
  sidebarOpen: boolean;
  timelinePoint: number | null;
  socialViewEnabled: boolean;
  setSelectedNode: (node: GraphNode | null) => void;
  setHoveredNode: (node: GraphNode | null) => void;
  setActiveClusterId: (clusterId: string | null) => void;
  setSidebarOpen: (open: boolean) => void;
  setTimelinePoint: (point: number | null) => void;
  setSocialViewEnabled: (enabled: boolean) => void;
}

export const useGraphStore = create<GraphState>((set) => ({
  selectedNode: null,
  hoveredNode: null,
  activeClusterId: null,
  sidebarOpen: false,
  timelinePoint: null,
  socialViewEnabled: false,
  setSelectedNode: (selectedNode) => set({ selectedNode }),
  setHoveredNode: (hoveredNode) => set({ hoveredNode }),
  setActiveClusterId: (activeClusterId) => set({ activeClusterId }),
  setSidebarOpen: (sidebarOpen) => set({ sidebarOpen }),
  setTimelinePoint: (timelinePoint) => set({ timelinePoint }),
  setSocialViewEnabled: (socialViewEnabled) => set({ socialViewEnabled }),
}));
