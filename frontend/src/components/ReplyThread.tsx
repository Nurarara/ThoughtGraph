import type { ReplyThread } from "../types";

interface ReplyThreadProps {
  thread: ReplyThread | null;
}

export function ReplyThread({ thread }: ReplyThreadProps) {
  if (!thread) {
    return (
      <div className="thread-shell">
        <p className="thread-empty">Replies appear here when thoughts start crossing between people.</p>
      </div>
    );
  }

  return (
    <div className="thread-shell">
      <div className="thread-root">
        <strong>{thread.root.author_display_name}</strong>
        <p>{thread.root.content}</p>
      </div>
      <div className="thread-list">
        {thread.replies.map((reply) => (
          <article key={reply.id} className="thread-reply">
            <strong>{reply.author_display_name}</strong>
            <p>{reply.content}</p>
            <small>{new Date(reply.created_at).toLocaleString()}</small>
          </article>
        ))}
      </div>
    </div>
  );
}
