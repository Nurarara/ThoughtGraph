import { useCallback, useEffect, useMemo, useState } from "react";

import { api, getWebSocketUrl } from "../api/client";
import type { GraphResponse, Insight, ThoughtInput } from "../types";

interface ThoughtGraphState {
  graph: GraphResponse | null;
  insights: Insight[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  seedDemo: () => Promise<number>;
  submitThought: (input: string | ThoughtInput) => Promise<void>;
  dismissInsight: (id: string) => Promise<void>;
  markInsightSeen: (id: string) => Promise<void>;
}

export function useThoughtGraph(socialEnabled: boolean): ThoughtGraphState {
  const [graph, setGraph] = useState<GraphResponse | null>(null);
  const [insights, setInsights] = useState<Insight[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setError(null);
      const [nextGraph, nextInsights] = await Promise.all([api.getGraph(socialEnabled), api.getInsights()]);
      setGraph(nextGraph);
      setInsights(nextInsights);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load ThoughtGraph.");
    } finally {
      setLoading(false);
    }
  }, [socialEnabled]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    const socket = new WebSocket(getWebSocketUrl());
    const interval = window.setInterval(() => {
      if (socket.readyState === WebSocket.OPEN) {
        socket.send("ping");
      }
    }, 15000);

    socket.addEventListener("message", () => {
      void refresh();
    });

    socket.addEventListener("error", () => {
      setError((current) => current ?? "Live updates are unavailable.");
    });

    return () => {
      window.clearInterval(interval);
      socket.close();
    };
  }, [refresh]);

  const actions = useMemo(
    () => ({
      async seedDemo() {
        try {
          setError(null);
          const result = await api.seedDemo();
          await refresh();
          return result.created;
        } catch (err) {
          setError(err instanceof Error ? err.message : "Failed to load seed thoughts.");
          throw err;
        }
      },
      async submitThought(input: string | ThoughtInput) {
        try {
          setError(null);
          await api.createThought(typeof input === "string" ? { content: input } : input);
          await refresh();
        } catch (err) {
          setError(err instanceof Error ? err.message : "Failed to create thought.");
          throw err;
        }
      },
      async dismissInsight(id: string) {
        try {
          setError(null);
          await api.dismissInsight(id);
          setInsights((current) => current.filter((insight) => insight.id !== id));
        } catch (err) {
          setError(err instanceof Error ? err.message : "Failed to dismiss insight.");
          throw err;
        }
      },
      async markInsightSeen(id: string) {
        try {
          setError(null);
          const updated = await api.markInsightSeen(id);
          setInsights((current) => current.map((item) => (item.id === id ? updated : item)));
        } catch (err) {
          setError(err instanceof Error ? err.message : "Failed to update insight.");
          throw err;
        }
      },
    }),
    [refresh],
  );

  return {
    graph,
    insights,
    loading,
    error,
    refresh,
    ...actions,
  };
}
