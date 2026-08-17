import { useEffect, useState } from "react";

import {
  graphApi,
  type PersistedReflectiveInsightRead,
  type ReflectiveCorrection,
  type ReflectiveFeedbackUpdate,
} from "../../lib/apiClient";

type AttentionDriftApi = Pick<
  typeof graphApi,
  "getReflectiveInsights" | "runReflectiveInsights" | "updateReflectiveInsightFeedback"
>;

interface AttentionDriftPanelProps {
  onFocusNode: (nodeId: string) => void;
  api?: AttentionDriftApi;
}

function formatMetric(value: number, unit: string) {
  if (["share", "ratio", "percent", "percentage"].includes(unit)) return `${Math.round(value * 100)}%`;
  if (unit === "count") return String(Math.round(value));
  return `${Number(value.toFixed(3))}${unit ? ` ${unit}` : ""}`;
}

function InsightCard({
  insight,
  api,
  onFocusNode,
  onUpdated,
}: {
  insight: PersistedReflectiveInsightRead;
  api: AttentionDriftApi;
  onFocusNode: (nodeId: string) => void;
  onUpdated: (insight: PersistedReflectiveInsightRead) => void;
}) {
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
          <strong>{insight.title}</strong>
          <span className={`phase-status ${insight.status === "ready" ? "phase-tone-good" : "phase-tone-watch"}`}>
            {insight.status === "ready" ? "ready" : "not enough data"}
          </span>
        </div>
        <time dateTime={insight.generated_at}>{new Date(insight.generated_at).toLocaleDateString()}</time>
      </div>
      <p>{insight.summary}</p>

      {insight.metrics.length ? (
        <div className="attention-metrics" aria-label="Attention drift metrics">
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
      ) : (
        <div className="attention-sparse" role="status">No comparison metric is available yet.</div>
      )}

      <div className="attention-confidence">
        <strong>{insight.confidence.label} confidence ({Math.round(insight.confidence.score * 100)}%)</strong>
        <span>{insight.confidence.basis}</span>
        <small>
          Sample {insight.confidence.sample_size}; minimum {insight.confidence.minimum_sample_size}
        </small>
      </div>

      <div className="attention-limitations">
        <strong>Limitations</strong>
        {insight.limitations.length ? (
          <ul>{insight.limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}</ul>
        ) : (
          <p>No additional limitations were supplied.</p>
        )}
      </div>

      {insight.evidence.length ? (
        <div className="attention-evidence">
          <strong>Evidence</strong>
          {insight.evidence.map((evidence) =>
            evidence.evidence_type === "node" ? (
              <button key={`${evidence.evidence_type}-${evidence.id}`} type="button" onClick={() => onFocusNode(evidence.id)}>
                <span>{evidence.label}</span>
                <small>{evidence.reason}</small>
              </button>
            ) : (
              <div className="attention-evidence-static" key={`${evidence.evidence_type}-${evidence.id}`}>
                <span>{evidence.label}</span>
                <small>{evidence.reason}</small>
              </div>
            ),
          )}
        </div>
      ) : null}

      {insight.action_hint ? <p className="attention-action"><strong>Possible next step:</strong> {insight.action_hint}</p> : null}

      <div className="attention-feedback">
        <label>
          <span>Correction</span>
          <select value={correction} onChange={(event) => setCorrection(event.currentTarget.value as ReflectiveCorrection | "")}>
            <option value="">No correction</option>
            <option value="inaccurate">Inaccurate</option>
            <option value="wrong_evidence">Wrong evidence</option>
            <option value="not_useful">Not useful</option>
          </select>
        </label>
        <label>
          <span>Annotation</span>
          <textarea
            value={annotation}
            maxLength={1000}
            rows={3}
            placeholder="Add context for your future self"
            onChange={(event) => setAnnotation(event.currentTarget.value)}
          />
        </label>
        <div className="attention-feedback-actions">
          <button
            type="button"
            disabled={saving}
            onClick={() => void updateFeedback({ correction: correction || null, annotation: annotation.trim() || null })}
          >
            {saving ? "Saving…" : "Save feedback"}
          </button>
          <button
            type="button"
            disabled={saving}
            onClick={() => void updateFeedback({ dismissed: !insight.feedback.dismissed })}
          >
            {insight.feedback.dismissed ? "Restore" : "Dismiss"}
          </button>
        </div>
        {saved ? <span role="status">Feedback saved.</span> : null}
        {feedbackError ? <span role="alert">{feedbackError}</span> : null}
      </div>
    </article>
  );
}

export function AttentionDriftPanel({ onFocusNode, api = graphApi }: AttentionDriftPanelProps) {
  const [insights, setInsights] = useState<PersistedReflectiveInsightRead[]>([]);
  const [includeDismissed, setIncludeDismissed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async (showDismissed = includeDismissed) => {
    setLoading(true);
    setError(null);
    try {
      setInsights(await api.getReflectiveInsights(showDismissed));
    } catch (loadError) {
      setInsights([]);
      setError(loadError instanceof Error ? loadError.message : "Could not load attention drift insights.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load(includeDismissed);
  }, [includeDismissed]);

  const run = async () => {
    setRunning(true);
    setError(null);
    try {
      await api.runReflectiveInsights();
      await load(includeDismissed);
    } catch (runError) {
      setError(runError instanceof Error ? runError.message : "Could not run attention drift analysis.");
    } finally {
      setRunning(false);
    }
  };

  const updateInsight = (updated: PersistedReflectiveInsightRead) => {
    setInsights((current) => {
      if (updated.feedback.dismissed && !includeDismissed) return current.filter((item) => item.id !== updated.id);
      return current.map((item) => item.id === updated.id ? updated : item);
    });
  };

  return (
    <div className="attention-drift-panel">
      <div className="attention-toolbar">
        <label>
          <input
            type="checkbox"
            checked={includeDismissed}
            onChange={(event) => setIncludeDismissed(event.currentTarget.checked)}
          />
          Show dismissed
        </label>
        <button type="button" disabled={running || loading} onClick={() => void run()}>
          {running ? "Running…" : "Run attention check"}
        </button>
      </div>
      {loading ? <div className="attention-state" role="status">Loading attention drift insights…</div> : null}
      {error ? <div className="attention-state phase-tone-danger" role="alert">{error}</div> : null}
      {!loading && !error && insights.length === 0 ? (
        <div className="attention-state">No attention drift insight exists yet. Run the check after saving thoughts over time.</div>
      ) : null}
      {!loading && !error ? (
        <div className="phase-insights">
          {insights.map((insight) => (
            <InsightCard key={insight.id} insight={insight} api={api} onFocusNode={onFocusNode} onUpdated={updateInsight} />
          ))}
        </div>
      ) : null}
    </div>
  );
}
