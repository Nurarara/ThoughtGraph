import { FormEvent, useState } from "react";

import { saveSession, thoughtApi } from "../lib/apiClient";
import type { SessionPayload } from "../lib/apiClient";

interface Props {
  onAuthenticated: (session: SessionPayload) => void;
  onClose: () => void;
}

export function AuthScreen({ onAuthenticated, onClose }: Props) {
  const [email, setEmail] = useState("");
  const [stage, setStage] = useState<"email" | "verify">("email");
  const [magicLink, setMagicLink] = useState<string | null>(null);
  const [token, setToken] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleRequestLink = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const response = await thoughtApi.requestMagicLink(email.trim());
      setMagicLink(response.magic_link);
      setStage("verify");
      if (response.magic_link) {
        try {
          const url = new URL(response.magic_link);
          const linkToken = url.searchParams.get("token");
          if (linkToken) setToken(linkToken);
        } catch {
          /* ignore */
        }
      }
    } catch (err) {
      setError((err as Error).message || "couldn't send link");
    } finally {
      setLoading(false);
    }
  };

  const handleVerify = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const session = await thoughtApi.verifyMagicToken(token.trim());
      saveSession(session);
      onAuthenticated(session);
    } catch (err) {
      setError((err as Error).message || "invalid token");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-backdrop" onClick={onClose}>
      <div className="auth-card" onClick={(e) => e.stopPropagation()}>
        <div className="auth-title">sign in to ThoughtGraph</div>
        <div className="auth-subtitle">
          {stage === "email"
            ? "enter your email — a sign-in link appears here (dev mode, no SMTP)."
            : "paste the token from the link to continue."}
        </div>

        {stage === "email" ? (
          <form className="auth-form" onSubmit={handleRequestLink}>
            <input
              autoFocus
              type="email"
              className="auth-input"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.currentTarget.value)}
              required
            />
            <button className="auth-submit" type="submit" disabled={loading}>
              {loading ? "sending…" : "send link"}
            </button>
          </form>
        ) : (
          <form className="auth-form" onSubmit={handleVerify}>
            {magicLink ? (
              <div className="auth-link-preview">
                <div className="auth-link-label">dev magic link</div>
                <a className="auth-link" href={magicLink} target="_blank" rel="noreferrer">
                  {magicLink}
                </a>
              </div>
            ) : null}
            <input
              autoFocus
              type="text"
              className="auth-input"
              placeholder="token"
              value={token}
              onChange={(e) => setToken(e.currentTarget.value)}
              required
              minLength={16}
            />
            <button className="auth-submit" type="submit" disabled={loading}>
              {loading ? "verifying…" : "verify"}
            </button>
            <button
              type="button"
              className="auth-secondary"
              onClick={() => {
                setStage("email");
                setToken("");
                setMagicLink(null);
              }}
            >
              use a different email
            </button>
          </form>
        )}

        {error ? <div className="auth-error">{error}</div> : null}
        <button className="auth-dismiss" onClick={onClose}>
          continue as guest
        </button>
      </div>
    </div>
  );
}
