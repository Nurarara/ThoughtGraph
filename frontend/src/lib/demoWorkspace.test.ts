// @vitest-environment jsdom

import { beforeEach, describe, expect, it } from "vitest";

import {
  DEMO_SESSION,
  addDemoNode,
  buildDemoDiscovery,
  buildDemoThread,
  isDemoSession,
  loadDemoGraph,
  searchDemoGraph,
} from "./demoWorkspace";

beforeEach(() => localStorage.clear());

describe("browser-local demo workspace", () => {
  it("starts with a connected, clustered field", () => {
    const graph = loadDemoGraph();
    expect(graph.nodes).toHaveLength(9);
    expect(graph.edges).toHaveLength(10);
    expect(graph.clusters).toHaveLength(3);
    expect(graph.nodes.every((node) => node.cluster_id && Number.isFinite(node.x) && Number.isFinite(node.y))).toBe(true);
  });

  it("adds and finds a local thought without mutating the fixture", () => {
    const graph = loadDemoGraph();
    const next = addDemoNode(graph, {
      kind: "thought",
      title: "A local experiment",
      content_text: "Prototype exploration should remain available without a server.",
      visibility: "private",
    });

    expect(graph.nodes).toHaveLength(9);
    expect(next.nodes).toHaveLength(10);
    expect(next.edges).toHaveLength(11);
    const newest = next.nodes[next.nodes.length - 1];
    expect(searchDemoGraph(next, "server")[0]?.node_id).toBe(newest.id);
    expect(buildDemoThread(next, newest.id)?.root.metadata_json).toEqual({ demo: true });

    const unsafeLink = addDemoNode(next, {
      kind: "link",
      title: "Unsafe protocol",
      link_url: "javascript:alert(1)",
      visibility: "private",
    });
    expect(unsafeLink.nodes[unsafeLink.nodes.length - 1].link_url).toBeNull();
  });

  it("keeps discovery honest and recognises migrated guest sessions", () => {
    const graph = loadDemoGraph();
    const discovery = buildDemoDiscovery(graph, "evidence");
    expect(discovery.items.length).toBeGreaterThan(0);
    expect(discovery.explanation_summary).toMatch(/browser-local/i);
    expect(isDemoSession(DEMO_SESSION)).toBe(true);
    expect(isDemoSession({ ...DEMO_SESSION, session_token: "old", user_id: "guest-old" })).toBe(true);
  });
});
