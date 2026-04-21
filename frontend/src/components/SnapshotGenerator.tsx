import { FormEvent, useState } from "react";

import type { Snapshot } from "../types";

interface SnapshotGeneratorProps {
  onCreate: (caption: string, isPublic: boolean) => Promise<Snapshot>;
}

export function SnapshotGenerator({ onCreate }: SnapshotGeneratorProps) {
  const [caption, setCaption] = useState("");
  const [isPublic, setIsPublic] = useState(true);
  const [creating, setCreating] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCreating(true);
    try {
      await onCreate(caption, isPublic);
      setCaption("");
    } finally {
      setCreating(false);
    }
  }

  return (
    <form className="page-card snapshot-generator" onSubmit={handleSubmit}>
      <div className="section-heading">
        <div>
          <p className="eyebrow">Snapshots</p>
          <h2>Capture your graph</h2>
        </div>
      </div>
      <input value={caption} onChange={(event) => setCaption(event.currentTarget.value)} placeholder="Caption this state of mind" />
      <label className="toggle-row">
        <span>Public snapshot</span>
        <input type="checkbox" checked={isPublic} onChange={(event) => setIsPublic(event.currentTarget.checked)} />
      </label>
      <button className="primary-button" type="submit" disabled={creating}>
        {creating ? "Capturing..." : "Capture snapshot"}
      </button>
    </form>
  );
}
