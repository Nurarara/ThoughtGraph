// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { PersistedReflectiveInsightRead, ReflectiveFeedbackUpdate } from "../../lib/apiClient";
import { AttentionDriftPanel } from "./AttentionDriftPanel";

afterEach(cleanup);

const readyInsight: PersistedReflectiveInsightRead = {
  id: "insight-1",
  kind: "attention_drift",
  contract_version: 1,
  title: "Attention moved toward graph reliability",
  summary: "Your saved nodes contain a larger share of reliability work than the comparison window.",
  generated_at: "2026-08-17T12:00:00Z",
  status: "ready",
  window: {
    current_start: "2026-08-10T00:00:00Z",
    current_end: "2026-08-17T00:00:00Z",
    comparison_start: "2026-08-03T00:00:00Z",
    comparison_end: "2026-08-10T00:00:00Z",
  },
  metrics: [{ key: "graph", label: "Graph share", current: 0.6, previous: 0.3, delta: 0.3, unit: "share", method: "Topic share by saved node" }],
  evidence: [{ evidence_type: "node", id: "node-1", label: "Projection integrity", reason: "Current-window graph node", created_at: null, metadata: {} }],
  confidence: { score: 0.8, label: "high", basis: "Enough nodes in both windows", sample_size: 10, minimum_sample_size: 6 },
  limitations: ["Saved nodes are not a complete measure of attention."],
  action_hint: "Review whether this change was intentional.",
  feedback: { dismissed: false, correction: null, annotation: null, updated_at: null },
};

function apiWith(insights: PersistedReflectiveInsightRead[]) {
  return {
    getReflectiveInsights: vi.fn(async () => insights),
    runReflectiveInsights: vi.fn(async () => ({ user_id: "u", generated_at: "", workflow_job_id: null, workflow_status: null, persisted_insight_ids: [] })),
    updateReflectiveInsightFeedback: vi.fn(async (_id: string, payload: ReflectiveFeedbackUpdate) => ({
      ...insights[0],
      feedback: { ...insights[0].feedback, ...payload, updated_at: "2026-08-17T12:01:00Z" },
    })),
  };
}

describe("AttentionDriftPanel", () => {
  it("renders backend metrics and focuses node evidence", async () => {
    const api = apiWith([readyInsight]);
    const onFocusNode = vi.fn();
    render(<AttentionDriftPanel api={api} onFocusNode={onFocusNode} />);

    expect(await screen.findByText(readyInsight.summary)).toBeInTheDocument();
    expect(screen.getByText("Current 60%")).toBeInTheDocument();
    expect(screen.getByText("Previous 30%")).toBeInTheDocument();
    expect(screen.getByText("Change +30%")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Projection integrity/i }));
    expect(onFocusNode).toHaveBeenCalledWith("node-1");
  });

  it("renders an honest insufficient-data state", async () => {
    const sparse = { ...readyInsight, id: "sparse", status: "insufficient_data" as const, metrics: [], summary: "There are not enough saved nodes in both windows.", confidence: { ...readyInsight.confidence, score: 0.2, label: "low" as const, sample_size: 2 } };
    render(<AttentionDriftPanel api={apiWith([sparse])} onFocusNode={() => undefined} />);

    expect(await screen.findByText("There are not enough saved nodes in both windows.")).toBeInTheDocument();
    expect(screen.getByText("not enough data")).toBeInTheDocument();
    expect(screen.getByRole("status", { name: "" })).toHaveTextContent("No comparison metric is available yet.");
    expect(screen.getByText(/Sample 2; minimum 6/)).toBeInTheDocument();
  });

  it("persists correction and annotation feedback", async () => {
    const api = apiWith([readyInsight]);
    render(<AttentionDriftPanel api={api} onFocusNode={() => undefined} />);
    await screen.findByText(readyInsight.summary);

    fireEvent.change(screen.getByLabelText("Correction"), { target: { value: "wrong_evidence" } });
    fireEvent.change(screen.getByLabelText("Annotation"), { target: { value: "This evidence misses planning notes." } });
    fireEvent.click(screen.getByRole("button", { name: "Save feedback" }));

    await waitFor(() => expect(api.updateReflectiveInsightFeedback).toHaveBeenCalledWith("insight-1", {
      correction: "wrong_evidence",
      annotation: "This evidence misses planning notes.",
    }));
    expect(await screen.findByText("Feedback saved.")).toBeInTheDocument();
  });

  it("shows API errors without rendering sample insights", async () => {
    const api = apiWith([]);
    api.getReflectiveInsights.mockRejectedValueOnce(new Error("reflection service unavailable"));
    render(<AttentionDriftPanel api={api} onFocusNode={() => undefined} />);

    expect(await screen.findByRole("alert")).toHaveTextContent("reflection service unavailable");
    expect(screen.queryByText(/recurring practical optimism/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/changing attention patterns/i)).not.toBeInTheDocument();
  });
});
