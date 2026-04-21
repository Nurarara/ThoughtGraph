import { MouseEvent, useState } from "react";

import type { UserProfile } from "../types";

interface SettingsPageProps {
  me: UserProfile | null;
  onUpdateNotificationPrefs: (payload: Record<string, boolean>) => Promise<void>;
  onUpdateVisibility: (visibility: "public" | "private") => Promise<void>;
  onUpdateOnboarding: (completed: boolean) => Promise<void>;
  onExport: () => Promise<Record<string, unknown>>;
}

export function SettingsPage({
  me,
  onUpdateNotificationPrefs,
  onUpdateVisibility,
  onUpdateOnboarding,
  onExport,
}: SettingsPageProps) {
  const [exportPreview, setExportPreview] = useState("");

  async function handleExport(event: MouseEvent<HTMLButtonElement>) {
    event.preventDefault();
    const data = await onExport();
    setExportPreview(JSON.stringify(data, null, 2));
  }

  return (
    <section className="page-grid">
      <section className="page-card">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Settings</p>
            <h2>Privacy and notifications</h2>
          </div>
        </div>
        <div className="settings-list">
          <label className="toggle-row">
            <span>Push replies</span>
            <input
              type="checkbox"
              checked={Boolean(me?.notification_prefs?.push_replies)}
              onChange={(event) => void onUpdateNotificationPrefs({ push_replies: event.currentTarget.checked })}
            />
          </label>
          <label className="toggle-row">
            <span>Push new followers</span>
            <input
              type="checkbox"
              checked={Boolean(me?.notification_prefs?.push_new_follower)}
              onChange={(event) => void onUpdateNotificationPrefs({ push_new_follower: event.currentTarget.checked })}
            />
          </label>
          <label className="toggle-row">
            <span>Email weekly report</span>
            <input
              type="checkbox"
              checked={Boolean(me?.notification_prefs?.email_weekly_report)}
              onChange={(event) => void onUpdateNotificationPrefs({ email_weekly_report: event.currentTarget.checked })}
            />
          </label>
          <div className="settings-actions">
            <button className="ghost-button" onClick={() => void onUpdateVisibility("private")}>
              Make all thoughts private
            </button>
            <button className="ghost-button" onClick={() => void onUpdateVisibility("public")}>
              Make all thoughts public
            </button>
            <button className="ghost-button" onClick={() => void onUpdateOnboarding(true)}>
              Mark onboarding complete
            </button>
            <button className="ghost-button" onClick={handleExport}>
              Export data
            </button>
          </div>
        </div>
        {exportPreview ? <pre className="export-preview">{exportPreview}</pre> : null}
      </section>
    </section>
  );
}
