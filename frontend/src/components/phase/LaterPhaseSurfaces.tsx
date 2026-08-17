import { motion } from "framer-motion";
import { ReflectiveInsightsPanel } from "./ReflectiveInsightsPanel";

import "../../phase.css";

type Tone = "good" | "watch" | "danger" | "neutral";

interface Metric {
  label: string;
  value: string;
  detail: string;
  tone?: Tone;
}

interface TimelineEvent {
  id: string;
  title: string;
  detail: string;
  at: string;
  tone?: Tone;
}

interface ReadModel {
  name: string;
  freshness: string;
  lag: string;
  coverage: number;
  status: Tone;
}

interface ProvenanceStep {
  label: string;
  actor: string;
  evidence: string;
  confidence: number;
}

interface GraphInspectorNode {
  id: string;
  label: string;
  kind: string;
  reads: string;
  writes: string;
  edges: number;
  drift: string;
}

interface ModerationItem {
  id: string;
  label: string;
  queue: string;
  severity: Tone;
  policy: string;
  volume: string;
}

interface ScaleRisk {
  system: string;
  pressure: string;
  ceiling: string;
  mitigation: string;
  tone: Tone;
}

const healthMetrics: Metric[] = [
  { label: "Event ingest", value: "99.98%", detail: "42k events / hour", tone: "good" },
  { label: "Projection lag", value: "1.8s", detail: "p95 across read models", tone: "watch" },
  { label: "Dead letters", value: "17", detail: "6 need replay review", tone: "danger" },
  { label: "Workflow jobs", value: "214", detail: "media, graph, digest", tone: "neutral" },
];

const healthEvents: TimelineEvent[] = [
  { id: "evt-1", title: "GraphProjectionCaughtUp", detail: "Cluster membership rebuilt for 18 hot topics.", at: "11:42", tone: "good" },
  { id: "evt-2", title: "SearchIndexBackpressure", detail: "Write fanout throttled after queue depth crossed 8k.", at: "11:31", tone: "watch" },
  { id: "evt-3", title: "MediaScanRetryExhausted", detail: "Three uploads moved to moderation quarantine.", at: "11:08", tone: "danger" },
];

const readModels: ReadModel[] = [
  { name: "Search materialization", freshness: "4s old", lag: "1.2s lag", coverage: 97, status: "good" },
  { name: "Discovery graph", freshness: "38s old", lag: "9.4s lag", coverage: 83, status: "watch" },
  { name: "Profile aggregates", freshness: "2m old", lag: "42s lag", coverage: 74, status: "danger" },
];

const provenanceSteps: ProvenanceStep[] = [
  { label: "Original thought", actor: "Mira Chen", evidence: "Signed node payload tg_91c", confidence: 99 },
  { label: "Semantic expansion", actor: "embedding-worker-04", evidence: "Model text-embedding-3-large", confidence: 94 },
  { label: "Cluster placement", actor: "graph-projector", evidence: "7 corroborating edges", confidence: 88 },
  { label: "Trust overlay", actor: "safety-ranker", evidence: "No policy conflicts, low bot affinity", confidence: 92 },
];

const inspectorNodes: GraphInspectorNode[] = [
  { id: "read:search", label: "Search Read Model", kind: "projection", reads: "DomainEvent", writes: "SearchDoc", edges: 12840, drift: "+0.6%" },
  { id: "read:cluster", label: "Cluster Read Model", kind: "projection", reads: "NodeEdge", writes: "NodeCluster", edges: 9340, drift: "-1.1%" },
  { id: "svc:moderation", label: "Moderation Gate", kind: "service", reads: "MediaAsset", writes: "UserRestriction", edges: 412, drift: "+3.4%" },
];

const moderationItems: ModerationItem[] = [
  { id: "mod-1", label: "Coordinated spam burst", queue: "Graph edges", severity: "danger", policy: "Manipulation", volume: "312 edges" },
  { id: "mod-2", label: "Sensitive media pending", queue: "Uploads", severity: "watch", policy: "Media safety", volume: "18 assets" },
  { id: "mod-3", label: "Appeal review", queue: "Restrictions", severity: "neutral", policy: "User action", volume: "7 cases" },
];

const scaleRisks: ScaleRisk[] = [
  { system: "Event bus", pressure: "72% partition saturation", ceiling: "120k events / min", mitigation: "Split social and graph topics", tone: "watch" },
  { system: "Vector index", pressure: "41ms p95 query", ceiling: "85ms SLO", mitigation: "Promote warm shards", tone: "good" },
  { system: "Projection workers", pressure: "13 retries / min", ceiling: "25 retries / min", mitigation: "Add idempotency audit", tone: "watch" },
  { system: "Media pipeline", pressure: "Queue age 14m", ceiling: "10m SLO", mitigation: "Burst scan workers", tone: "danger" },
];

function toneClass(tone: Tone = "neutral") {
  return `phase-tone-${tone}`;
}

function PhaseShell({ title, eyebrow, children }: { title: string; eyebrow: string; children: React.ReactNode }) {
  return (
    <motion.section
      className="phase-panel"
      initial={{ opacity: 0, y: 18 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.32, ease: "easeOut" }}
    >
      <div className="phase-panel__header">
        <div>
          <p className="phase-eyebrow">{eyebrow}</p>
          <h2>{title}</h2>
        </div>
      </div>
      {children}
    </motion.section>
  );
}

export function OperationsEventHealth() {
  return (
    <PhaseShell eyebrow="Phase 6 / Event Spine" title="Operations and event health">
      <div className="phase-metric-grid">
        {healthMetrics.map((metric) => (
          <article className={`phase-metric ${toneClass(metric.tone)}`} key={metric.label}>
            <span>{metric.label}</span>
            <strong>{metric.value}</strong>
            <small>{metric.detail}</small>
          </article>
        ))}
      </div>
      <div className="phase-event-rail">
        {healthEvents.map((event) => (
          <div className="phase-event" key={event.id}>
            <span className={`phase-pulse ${toneClass(event.tone)}`} />
            <div>
              <strong>{event.title}</strong>
              <p>{event.detail}</p>
            </div>
            <time>{event.at}</time>
          </div>
        ))}
      </div>
    </PhaseShell>
  );
}

export function SearchReadModelStatus() {
  return (
    <PhaseShell eyebrow="Phase 7 / Search" title="Read model status">
      <div className="phase-readmodels">
        {readModels.map((model) => (
          <article className="phase-readmodel" key={model.name}>
            <div className="phase-row">
              <div>
                <strong>{model.name}</strong>
                <p>{model.freshness} / {model.lag}</p>
              </div>
              <span className={`phase-status ${toneClass(model.status)}`}>{model.status}</span>
            </div>
            <div className="phase-progress" aria-label={`${model.coverage}% coverage`}>
              <span style={{ width: `${model.coverage}%` }} />
            </div>
            <small>{model.coverage}% indexed coverage</small>
          </article>
        ))}
      </div>
    </PhaseShell>
  );
}

export function ProvenanceTrustDrawer() {
  return (
    <PhaseShell eyebrow="Phase 8 / Trust" title="Provenance and trust drawer">
      <div className="phase-trust-score">
        <span>Trust posture</span>
        <strong>92</strong>
        <p>High confidence, transparent derivation, no unresolved safety flags.</p>
      </div>
      <div className="phase-provenance">
        {provenanceSteps.map((step) => (
          <article className="phase-provenance-step" key={step.label}>
            <div>
              <strong>{step.label}</strong>
              <p>{step.actor}</p>
              <small>{step.evidence}</small>
            </div>
            <span>{step.confidence}%</span>
          </article>
        ))}
      </div>
    </PhaseShell>
  );
}

export function GraphReadModelInspector() {
  return (
    <PhaseShell eyebrow="Phase 9 / Inspector" title="Graph read model inspector">
      <div className="phase-node-map">
        {inspectorNodes.map((node, index) => (
          <article className="phase-node-card" key={node.id} style={{ "--phase-index": index } as React.CSSProperties}>
            <span>{node.kind}</span>
            <strong>{node.label}</strong>
            <dl>
              <div><dt>Reads</dt><dd>{node.reads}</dd></div>
              <div><dt>Writes</dt><dd>{node.writes}</dd></div>
              <div><dt>Edges</dt><dd>{node.edges.toLocaleString()}</dd></div>
              <div><dt>Drift</dt><dd>{node.drift}</dd></div>
            </dl>
          </article>
        ))}
      </div>
    </PhaseShell>
  );
}

export function ReflectiveInsights({ onFocusNode }: { onFocusNode: (nodeId: string) => void }) {
  return (
    <PhaseShell eyebrow="Phase 10 / Reflection" title="Reflective insights">
      <ReflectiveInsightsPanel onFocusNode={onFocusNode} />
    </PhaseShell>
  );
}

export function ModerationControls() {
  return (
    <PhaseShell eyebrow="Phase 11 / Safety" title="Moderation controls">
      <div className="phase-controls">
        {moderationItems.map((item) => (
          <article className={`phase-control ${toneClass(item.severity)}`} key={item.id}>
            <div>
              <span>{item.queue}</span>
              <strong>{item.label}</strong>
              <p>{item.policy} / {item.volume}</p>
            </div>
            <div className="phase-control__actions">
              <button type="button">Inspect</button>
              <button type="button">Throttle</button>
            </div>
          </article>
        ))}
      </div>
    </PhaseShell>
  );
}

export function ScaleHardeningDashboard() {
  return (
    <PhaseShell eyebrow="Phase 12 / Hardening" title="Scale hardening dashboard">
      <div className="phase-scale-grid">
        {scaleRisks.map((risk) => (
          <article className={`phase-scale-card ${toneClass(risk.tone)}`} key={risk.system}>
            <div className="phase-row">
              <strong>{risk.system}</strong>
              <span>{risk.pressure}</span>
            </div>
            <p>Ceiling: {risk.ceiling}</p>
            <small>{risk.mitigation}</small>
          </article>
        ))}
      </div>
    </PhaseShell>
  );
}

export function LaterPhaseCommandCenter({ onFocusNode }: { onFocusNode: (nodeId: string) => void }) {
  return (
    <main className="phase-command-center">
      <section className="phase-hero">
        <p className="phase-eyebrow">ThoughtGraph / Phases 6-12</p>
        <h1>Later-phase operational surfaces</h1>
        <p>
          Prototype-ready panels for the systems that make a graph-native product reliable: events, projections,
          provenance, reflection, safety, and scale.
        </p>
      </section>
      <div className="phase-dashboard-grid">
        <OperationsEventHealth />
        <SearchReadModelStatus />
        <ProvenanceTrustDrawer />
        <GraphReadModelInspector />
        <ReflectiveInsights onFocusNode={onFocusNode} />
        <ModerationControls />
        <ScaleHardeningDashboard />
      </div>
    </main>
  );
}
