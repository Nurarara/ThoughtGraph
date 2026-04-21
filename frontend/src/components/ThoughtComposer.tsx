import { FormEvent, useState } from "react";

import type { ThoughtInput } from "../types";

interface ThoughtComposerProps {
  onSubmit: (input: ThoughtInput) => Promise<void>;
  disabled?: boolean;
}

export function ThoughtComposer({ onSubmit, disabled }: ThoughtComposerProps) {
  const [content, setContent] = useState("");
  const [visibility, setVisibility] = useState<"public" | "private">("public");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!content.trim()) {
      return;
    }
    setSubmitting(true);
    try {
      await onSubmit({ content: content.trim(), visibility });
      setContent("");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="thought-composer" onSubmit={handleSubmit}>
      <div className="thought-composer-main">
        <label className="sr-only" htmlFor="thought-input">
          Thought input
        </label>
        <input
          id="thought-input"
          value={content}
          onChange={(event) => setContent(event.currentTarget.value)}
          placeholder="What has been shaping your mind lately?"
          disabled={disabled || submitting}
        />
      </div>
      <div className="thought-composer-actions">
        <select value={visibility} onChange={(event) => setVisibility(event.currentTarget.value as "public" | "private")}>
          <option value="public">Public</option>
          <option value="private">Private</option>
        </select>
        <button type="submit" disabled={disabled || submitting || !content.trim()}>
          {submitting ? "Tracing..." : "Commit Thought"}
        </button>
      </div>
    </form>
  );
}
