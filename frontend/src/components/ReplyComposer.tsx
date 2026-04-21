import { FormEvent, useState } from "react";

import type { ThoughtInput } from "../types";

interface ReplyComposerProps {
  targetThoughtId: string;
  onSubmit: (input: ThoughtInput) => Promise<void>;
}

export function ReplyComposer({ targetThoughtId, onSubmit }: ReplyComposerProps) {
  const [content, setContent] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!content.trim()) {
      return;
    }
    setSubmitting(true);
    try {
      await onSubmit({ content: content.trim(), reply_to_id: targetThoughtId, visibility: "public" });
      setContent("");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="reply-composer" onSubmit={handleSubmit}>
      <input
        value={content}
        onChange={(event) => setContent(event.currentTarget.value)}
        placeholder="Reply into the thread..."
        disabled={submitting}
      />
      <button type="submit" disabled={submitting || !content.trim()}>
        {submitting ? "Sending..." : "Reply"}
      </button>
    </form>
  );
}
