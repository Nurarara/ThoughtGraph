// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { PersistedReflectiveInsightRead, ReflectiveFeedbackUpdate } from "../../lib/apiClient";
import { ReflectiveInsightsPanel } from "./ReflectiveInsightsPanel";

afterEach(cleanup);

const attention: PersistedReflectiveInsightRead = {
  id: "attention-1", kind: "attention_drift", contract_version: 1,
  title: "Attention moved toward graph reliability", summary: "A larger share concerns reliability.",
  generated_at: "2026-08-17T12:00:00Z", status: "ready",
  window: { current_start: "2026-08-10T00:00:00Z", current_end: "2026-08-17T00:00:00Z", comparison_start: "2026-08-03T00:00:00Z", comparison_end: "2026-08-10T00:00:00Z" },
  metrics: [{ key: "graph", label: "Graph share", current: .6, previous: .3, delta: .3, unit: "share", method: "Topic share by saved node" }],
  evidence: [{ evidence_type: "node", id: "node-1", label: "Projection integrity", reason: "Current-window node", created_at: null, metadata: {} }],
  confidence: { score: .8, label: "high", basis: "Enough nodes in both windows", sample_size: 10, minimum_sample_size: 6 },
  limitations: ["Saved nodes are not a complete measure of attention."], action_hint: "Review whether this was intentional.",
  feedback: { dismissed: false, correction: null, annotation: null, updated_at: null },
};

const source: PersistedReflectiveInsightRead = {
  ...attention, id: "source-1", kind: "source_shaping_summary", title: "Source-Shaping Summary",
  summary: "Among your saved inputs, links are dominant.",
  metrics: [
    { key: "dominant_input_kind_share", label: "Share of link inputs", current: 1, previous: .5, delta: .5, unit: "proportion", method: "Count input kinds." },
    { key: "top_source_domain_count", label: "Saved links from news.example", current: 3, previous: 1, delta: 2, unit: "nodes", method: "Count normalized hostnames." },
  ],
  evidence: [
    { evidence_type: "node", id: "node-source", label: "Saved article", reason: "source mix sample", created_at: null, metadata: {} },
    { evidence_type: "source", id: "news.example", label: "news.example", reason: "most repeated domain", created_at: null, metadata: { count: 3 } },
  ],
  confidence: { score: .7, label: "medium", basis: "Saved-node counts; not proof of influence.", sample_size: 7, minimum_sample_size: 6 },
  limitations: ["This does not establish influence."], action_hint: "Add a contrasting input.",
};

function apiWith(rows: PersistedReflectiveInsightRead[]) {
  let current = rows;
  return {
    getReflectiveInsights: vi.fn(async (includeDismissed = false) => current.filter((item) => includeDismissed || !item.feedback.dismissed)),
    runReflectiveInsights: vi.fn(async () => ({ user_id: "u", generated_at: "", workflow_job_id: null, workflow_status: null, persisted_insight_ids: [] })),
    updateReflectiveInsightFeedback: vi.fn(async (id: string, payload: ReflectiveFeedbackUpdate) => {
      const existing = current.find((item) => item.id === id)!;
      const updated = { ...existing, feedback: { ...existing.feedback, ...payload, updated_at: "2026-08-17T12:01:00Z" } };
      current = current.map((item) => item.id === id ? updated : item);
      return updated;
    }),
  };
}

describe("ReflectiveInsightsPanel", () => {
  it("preserves attention evidence focus and feedback behavior", async () => {
    const api = apiWith([attention]);
    const focus = vi.fn();
    render(<ReflectiveInsightsPanel api={api} onFocusNode={focus} />);
    fireEvent.click(await screen.findByRole("button", { name: /Projection integrity/i }));
    expect(focus).toHaveBeenCalledWith("node-1");
    fireEvent.change(screen.getByLabelText("Correction"), { target: { value: "wrong_evidence" } });
    fireEvent.change(screen.getByLabelText("Annotation"), { target: { value: "Planning notes are missing." } });
    fireEvent.click(screen.getByRole("button", { name: "Save feedback" }));
    await waitFor(() => expect(api.updateReflectiveInsightFeedback).toHaveBeenCalledWith("attention-1", {
      correction: "wrong_evidence", annotation: "Planning notes are missing.",
    }));
  });

  it("renders mixed kinds, exact source units, and preserves attention metrics", async () => {
    render(<ReflectiveInsightsPanel api={apiWith([attention, source])} onFocusNode={() => undefined} />);
    expect(await screen.findByText(attention.summary)).toBeInTheDocument();
    expect(screen.getByText(source.summary)).toBeInTheDocument();
    expect(screen.getByText("Current 60%")).toBeInTheDocument();
    const sourceMetrics = screen.getByLabelText("Source-shaping metrics");
    expect(within(sourceMetrics).getByText("Current 100%")).toBeInTheDocument();
    expect(within(sourceMetrics).getByText("Previous 1 nodes")).toBeInTheDocument();
    expect(within(sourceMetrics).getByText("Change +2 nodes")).toBeInTheDocument();
  });

  it("focuses node evidence but renders source-domain evidence as non-clickable", async () => {
    const focus = vi.fn();
    render(<ReflectiveInsightsPanel api={apiWith([source])} onFocusNode={focus} />);
    fireEvent.click(await screen.findByRole("button", { name: /Saved article/i }));
    expect(focus).toHaveBeenCalledWith("node-source");
    expect(screen.queryByRole("button", { name: /news\.example/i })).not.toBeInTheDocument();
    expect(screen.getByText("news.example")).toBeInTheDocument();
  });

  it("persists source feedback against the source insight", async () => {
    const api = apiWith([source]);
    render(<ReflectiveInsightsPanel api={api} onFocusNode={() => undefined} />);
    await screen.findByText(source.summary);
    fireEvent.change(screen.getByLabelText("Correction"), { target: { value: "not_useful" } });
    fireEvent.change(screen.getByLabelText("Annotation"), { target: { value: "File type is not a source." } });
    fireEvent.click(screen.getByRole("button", { name: "Save feedback" }));
    await waitFor(() => expect(api.updateReflectiveInsightFeedback).toHaveBeenCalledWith("source-1", { correction: "not_useful", annotation: "File type is not a source." }));
    expect(await screen.findByText("Feedback saved.")).toBeInTheDocument();
  });

  it("dismisses one kind and reloads dismissed rows on request", async () => {
    const api = apiWith([attention, source]);
    render(<ReflectiveInsightsPanel api={api} onFocusNode={() => undefined} />);
    await screen.findByText(source.summary);
    const sourceCard = screen.getByText(source.title).closest("article")!;
    fireEvent.click(within(sourceCard).getByRole("button", { name: "Dismiss" }));
    await waitFor(() => expect(screen.queryByText(source.summary)).not.toBeInTheDocument());
    expect(screen.getByText(attention.summary)).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Show dismissed"));
    expect(await screen.findByText(source.summary)).toBeInTheDocument();
    expect(api.getReflectiveInsights).toHaveBeenLastCalledWith(true);
  });

  it("renders an honest sparse source state", async () => {
    const sparse = { ...source, status: "insufficient_data" as const, metrics: [], evidence: [], summary: "There is not enough saved activity in both windows.", confidence: { ...source.confidence, score: 0, label: "low" as const, sample_size: 2 } };
    render(<ReflectiveInsightsPanel api={apiWith([sparse])} onFocusNode={() => undefined} />);
    expect(await screen.findByText(sparse.summary)).toBeInTheDocument();
    expect(screen.getByText("not enough data")).toBeInTheDocument();
    expect(screen.getByText("No comparison metric is available yet.")).toBeInTheDocument();
    expect(screen.getByText(/Sample 2; minimum 6/)).toBeInTheDocument();
  });

  it("shows API errors without sample fallback", async () => {
    const api = apiWith([]);
    api.getReflectiveInsights.mockRejectedValueOnce(new Error("reflection service unavailable"));
    render(<ReflectiveInsightsPanel api={api} onFocusNode={() => undefined} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("reflection service unavailable");
    expect(screen.queryByText(/recurring practical optimism/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/changing attention patterns/i)).not.toBeInTheDocument();
  });

  it("renders an honest empty state", async () => {
    render(<ReflectiveInsightsPanel api={apiWith([])} onFocusNode={() => undefined} />);
    expect(await screen.findByText("No reflective insights exist yet. Run reflection after saving thoughts over time.")).toBeInTheDocument();
  });

  it("runs reflection and refreshes both kinds", async () => {
    const api = apiWith([attention, source]);
    render(<ReflectiveInsightsPanel api={api} onFocusNode={() => undefined} />);
    await screen.findByText(source.summary);
    fireEvent.click(screen.getByRole("button", { name: "Run reflection" }));
    await waitFor(() => expect(api.runReflectiveInsights).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(api.getReflectiveInsights).toHaveBeenCalledTimes(2));
    expect(screen.getByText(attention.summary)).toBeInTheDocument();
    expect(screen.getByText(source.summary)).toBeInTheDocument();
  });
});
