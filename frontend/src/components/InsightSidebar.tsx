import { AnimatePresence, motion } from "framer-motion";

import type { GraphCluster, Insight } from "../types";

interface InsightSidebarProps {
  insights: Insight[];
  clusters: GraphCluster[];
  activeClusterId: string | null;
  onDismissInsight: (id: string) => Promise<void>;
  onSelectCluster: (clusterId: string | null) => void;
  onOpenInsight: (id: string) => Promise<void>;
  seedDemo: () => Promise<number>;
  isEmpty: boolean;
}

const INSIGHT_ACCENTS: Record<string, string> = {
  focus_shift: "var(--accent-violet)",
  emotional_pattern: "var(--accent-pink)",
  echo_chamber: "var(--accent-orange)",
};

export function InsightSidebar({
  insights,
  clusters,
  activeClusterId,
  onDismissInsight,
  onSelectCluster,
  onOpenInsight,
  seedDemo,
  isEmpty,
}: InsightSidebarProps) {
  return (
    <aside className="sidebar-panel">
      <div className="sidebar-section">
        <div className="sidebar-heading">
          <div>
            <p className="eyebrow">Insight Layer</p>
            <h2>What your graph is quietly saying</h2>
          </div>
          {activeClusterId ? (
            <button className="ghost-button" onClick={() => onSelectCluster(null)}>
              Reset focus
            </button>
          ) : null}
        </div>

        {isEmpty ? (
          <div className="empty-panel">
            <p>Start with seed thoughts or post your own. The graph becomes interesting once it has enough tension to reveal a pattern.</p>
            <button className="primary-button" onClick={() => void seedDemo()}>
              Load seeded mind
            </button>
          </div>
        ) : (
          <div className="insight-stack">
            <AnimatePresence mode="popLayout">
              {insights.slice(0, 3).map((insight) => (
                <motion.article
                  key={insight.id}
                  className="insight-card"
                  drag="x"
                  dragConstraints={{ left: 0, right: 0 }}
                  onClick={() => void onOpenInsight(insight.id)}
                  onDragEnd={(_, info) => {
                    if (Math.abs(info.offset.x) > 120) {
                      void onDismissInsight(insight.id);
                    }
                  }}
                  initial={{ opacity: 0, y: 24 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, x: -120 }}
                  transition={{ duration: 0.35, ease: "easeOut" }}
                >
                  <span className="insight-accent" style={{ background: INSIGHT_ACCENTS[insight.kind] ?? "var(--accent-cyan)" }} />
                  <p>{insight.content}</p>
                  <div className="insight-meta">
                    <span>{new Date(insight.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}</span>
                    <span>{insight.kind.replace(/_/g, " ")}</span>
                  </div>
                </motion.article>
              ))}
            </AnimatePresence>
          </div>
        )}
      </div>

      <div className="sidebar-section">
        <div className="sidebar-heading compact">
          <div>
            <p className="eyebrow">Cluster Map</p>
            <h3>Dominant lines of thought</h3>
          </div>
        </div>
        <div className="cluster-list">
          {clusters.map((cluster) => (
            <button
              key={cluster.id}
              className={`cluster-row ${activeClusterId === cluster.id ? "active" : ""}`}
              onClick={() => onSelectCluster(activeClusterId === cluster.id ? null : cluster.id)}
            >
              <span className="cluster-dot" style={{ background: cluster.color }} />
              <span className="cluster-copy">
                <strong>{cluster.label}</strong>
                <small>
                  {Math.round(cluster.percentage * 100)}% of thoughts - {cluster.trend}
                </small>
              </span>
            </button>
          ))}
        </div>
      </div>
    </aside>
  );
}
