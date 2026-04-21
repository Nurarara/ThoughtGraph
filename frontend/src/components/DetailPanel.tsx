import { motion } from "framer-motion";

import { ReplyComposer } from "./ReplyComposer";
import { ReplyThread } from "./ReplyThread";
import type { GraphNode } from "../types";
import type { ReplyThread as ReplyThreadModel, ThoughtInput } from "../types";

interface DetailPanelProps {
  node: GraphNode | null;
  thread: ReplyThreadModel | null;
  onReply: (input: ThoughtInput) => Promise<void>;
  onClose: () => void;
}

export function DetailPanel({ node, thread, onReply, onClose }: DetailPanelProps) {
  if (!node) {
    return null;
  }

  return (
    <motion.aside
      className="detail-panel"
      initial={{ x: 40, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      exit={{ x: 40, opacity: 0 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
    >
      <div className="detail-header">
        <div>
          <p className="eyebrow">Thought Detail</p>
          <h3>{node.cluster_label ?? "Unclustered"}</h3>
        </div>
        <button className="ghost-button" onClick={onClose}>
          Close
        </button>
      </div>

      <p className="detail-content">{node.content}</p>

      <div className="detail-tags">
        {node.topics.map((topic) => (
          <span key={topic}>{topic}</span>
        ))}
        <span>{node.emotion}</span>
        {node.author_display_name ? <span>{node.author_display_name}</span> : null}
      </div>

      <dl className="detail-metadata">
        <div>
          <dt>Created</dt>
          <dd>{new Date(node.created_at).toLocaleString()}</dd>
        </div>
        <div>
          <dt>Connections</dt>
          <dd>{node.connection_count}</dd>
        </div>
        <div>
          <dt>Activity score</dt>
          <dd>{node.activity_score}</dd>
        </div>
      </dl>

      <div className="detail-thread-block">
        <p className="eyebrow">Thread</p>
        <ReplyComposer targetThoughtId={node.id} onSubmit={onReply} />
        <ReplyThread thread={thread} />
      </div>
    </motion.aside>
  );
}
