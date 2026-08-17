import { useEffect, useState } from "react";

import {
  graphApi,
  type PersistedReflectiveInsightRead,
  type ReflectiveCorrection,
  type ReflectiveFeedbackUpdate,
} from "../../lib/apiClient";

export type ReflectiveInsightsApi = Pick<
  typeof graphApi,
  "getReflectiveInsights" | "runReflectiveInsights" | "updateReflectiveInsightFeedback"
>;

interface Props {
  onFocusNode: (nodeId: string) => void;
  api?: ReflectiveInsightsApi;
}

function presentation(kind: PersistedReflectiveInsightRead["kind"]) {
  switch (kind) {
    case "attention_drift":
      return { label: "Attention drift", metricsLabel: "Attention drift metrics" };
    case "source_shaping_summary":
      return { label: "Source shaping", metricsLabel: "Source-shaping metrics" };
    default: {
      const exhaustive: never = kind;
      return exhaustive;
    }
  }
}

function formatMetric(value: number, unit: string) {
  if (["share", "ratio", "percent", "percentage", "proportion"].includes(unit)) {
    return `${Math.round(value * 100)}%`;
  }
  if (["count", "nodes"].includes(unit)) return `${Math.round(value)}${unit === "nodes" ? " nodes" : ""}`;
  return `${Number(value.toFixed(3))}${unit ? ` ${unit}` : ""}`;
}

function ReflectiveInsightCard({ insight, api, onFocusNode, onUpdated }: {
  insight: PersistedReflectiveInsightRead;
  api: ReflectiveInsightsApi;
  onFocusNode: (nodeId: string) => void;
  onUpdated: (insight: PersistedReflectiveInsightRead) => void;
}) {
  const copy = presentation(insight.kind);
  const [correction, setCorrection] = useState<ReflectiveCorrection | "">(insight.feedback.correction ?? "");
  const [annotation, setAnnotation] = useState(insight.feedback.annotation ?? "");
  const [saving, setSaving] = useState(false);
  const [feedbackError, setFeedbackError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setCorrection(insight.feedback.correction ?? "");
    setAnnotation(insight.feedback.annotation ?? "");
  }, [insight.feedback.annotation, insight.feedback.correction]);

  const updateFeedback = async (payload: ReflectiveFeedbackUpdate) => {
    setSaving(true);
    setSaved(false);
    setFeedbackError(null);
    try {
      const updated = await api.updateReflectiveInsightFeedback(insight.id, payload);
      onUpdated(updated);
      setSaved(true);
    } catch (error) {
      setFeedbackError(error instanceof Error ? error.message : "Could not save feedback.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <article className={`phase-insight attention-insight ${insight.feedback.dismissed ? "is-dismissed" : ""}`}>
      <div className="phase-row">
        <div>
          <small className="attention-kind">{copy.label}</small>
          <strong>{insight.title}</strong>
          <span className={`phase-status ${insight.status === "ready" ? "phase-tone-good" : "phase-tone-watch"}`}>
            {insight.status === "ready" ? "ready" : "not enough data"}
          </span>
        </div>
        <time dateTime={insight.generated_at}>{new Date(insight.generated_at).toLocaleDateString()}</time>
      </div>
      <p>{insight.summary}</p>
      {insight.metrics.length ? (
        <div className="attention-metrics" aria-label={copy.metricsLabel}>
          {insight.metrics.map((metric) => (
            <div className="attention-metric" key={metric.key}>
              <strong>{metric.label}</strong>
              <span>Current {formatMetric(metric.current, metric.unit)}</span>
              <span>Previous {formatMetric(metric.previous, metric.unit)}</span>
              <span>Change {metric.delta > 0 ? "+" : ""}{formatMetric(metric.delta, metric.unit)}</span>
              <small>{metric.method}</small>
            </div>
          ))}
        </div>
      ) : <div className="attention-sparse" role="status">No comparison metric is available yet.</div>}
      <div className="attention-confidence">
        <strong>{insight.confidence.label} confidence ({Math.round(insight.confidence.score * 100)}%)</strong>
        <span>{insight.confidence.basis}</span>
        <small>Sample {insight.confidence.sample_size}; minimum {insight.confidence.minimum_sample_size}</small>
      </div>
      <div className="attention-limitations">
        <strong>Limitations</strong>
        {insight.limitations.length ? <ul>{insight.limitations.map((item) => <li key={item}>{item}</li>)}</ul> : <p>No additional limitations were supplied.</p>}
      </div>
      {insight.evidence.length ? (
        <div className="attention-evidence">
          <strong>Evidence</strong>
          {insight.evidence.map((item) => item.evidence_type === "node" ? (
            <button key={`node-${item.id}`} type="button" onClick={() => onFocusNode(item.id)}>
              <span>{item.label}</span><small>{item.reason}</small>
            </button>
          ) : (
            <div className="attention-evidence-static" key={`${item.evidence_type}-${item.id}`}>
              <span>{item.label}</span><small>{item.reason}</small>
            </div>
          ))}
        </div>
      ) : null}
      {insight.action_hint ? <p className="attention-action"><strong>Possible next step:</strong> {insight.action_hint}</p> : null}
      <div className="attention-feedback">
        <label><span>Correction</span><select value={correction} onChange={(event) => setCorrection(event.currentTarget.value as ReflectiveCorrection | "")}>
          <option value="">No correction</option><option value="inaccurate">Inaccurate</option>
          <option value="wrong_evidence">Wrong evidence</option><option value="not_useful">Not useful</option>
        </select></label>
        <label><span>Annotation</span><textarea value={annotation} maxLength={1000} rows={3} placeholder="Add context for your future self" onChange={(event) => setAnnotation(event.currentTarget.value)} /></label>
        <div className="attention-feedback-actions">
          <button type="button" disabled={saving} onClick={() => void updateFeedback({ correction: correction || null, annotation: annotation.trim() || null })}>{saving ? "Saving…" : "Save feedback"}</button>
          <button type="button" disabled={saving} onClick={() => void updateFeedback({ dismissed: !insight.feedback.dismissed })}>{insight.feedback.dismissed ? "Restore" : "Dismiss"}</button>
        </div>
        {saved ? <span role="status">Feedback saved.</span> : null}
        {feedbackError ? <span role="alert">{feedbackError}</span> : null}
      </div>
    </article>
  );
}

export function ReflectiveInsightsPanel({ onFocusNode, api = graphApi }: Props) {
  const [insights, setInsights] = useState<PersistedReflectiveInsightRead[]>([]);
  const [includeDismissed, setIncludeDismissed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async (showDismissed = includeDismissed) => {
    setLoading(true); setError(null);
    try { setInsights(await api.getReflectiveInsights(showDismissed)); }
    catch (loadError) {
      setInsights([]);
      setError(loadError instanceof Error ? loadError.message : "Could not load reflective insights.");
    } finally { setLoading(false); }
  };

  useEffect(() => { void load(includeDismissed); }, [includeDismissed]);

  const run = async () => {
    setRunning(true); setError(null);
    try { await api.runReflectiveInsights(); await load(includeDismissed); }
    catch (runError) { setError(runError instanceof Error ? runError.message : "Could not run reflection."); }
    finally { setRunning(false); }
  };

  const updateInsight = (updated: PersistedReflectiveInsightRead) => setInsights((current) => {
    if (updated.feedback.dismissed && !includeDismissed) return current.filter((item) => item.id !== updated.id);
    return current.map((item) => item.id === updated.id ? updated : item);
  });

  return <div className="attention-drift-panel">
    <div className="attention-toolbar">
      <label><input type="checkbox" checked={includeDismissed} onChange={(event) => setIncludeDismissed(event.currentTarget.checked)} />Show dismissed</label>
      <button type="button" disabled={running || loading} onClick={() => void run()}>{running ? "Running…" : "Run reflection"}</button>
    </div>
    {loading ? <div className="attention-state" role="status">Loading reflective insights…</div> : null}
    {error ? <div className="attention-state phase-tone-danger" role="alert">{error}</div> : null}
    {!loading && !error && insights.length === 0 ? <div className="attention-state">No reflective insights exist yet. Run reflection after saving thoughts over time.</div> : null}
    {!loading && !error ? <div className="phase-insights">{insights.map((insight) => <ReflectiveInsightCard key={insight.id} insight={insight} api={api} onFocusNode={onFocusNode} onUpdated={updateInsight} />)}</div> : null}
  </div>;
}
