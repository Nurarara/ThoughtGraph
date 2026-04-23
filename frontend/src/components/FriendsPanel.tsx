import { useCallback, useEffect, useState } from "react";

import { thoughtApi } from "../lib/apiClient";
import type {
  FriendsListResponse,
  FriendSummary,
  UserSearchResult,
} from "../lib/apiClient";

interface Props {
  open: boolean;
  onClose: () => void;
  onFriendsChanged?: () => void;
  onOpenProfile?: (userId: string) => void;
}

export function FriendsPanel({ open, onClose, onFriendsChanged, onOpenProfile }: Props) {
  const [data, setData] = useState<FriendsListResponse | null>(null);
  const [suggestions, setSuggestions] = useState<FriendSummary[]>([]);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<UserSearchResult[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [friends, sugg] = await Promise.all([
        thoughtApi.getFriends(),
        thoughtApi.getFriendSuggestions().catch(() => []),
      ]);
      setData(friends);
      setSuggestions(sugg);
    } catch (err) {
      setError((err as Error).message);
    }
  }, []);

  useEffect(() => {
    if (open) {
      refresh();
    }
  }, [open, refresh]);

  useEffect(() => {
    if (!open) return;
    const handle = setTimeout(async () => {
      if (query.trim().length === 0) {
        setResults([]);
        return;
      }
      try {
        const found = await thoughtApi.searchUsers(query.trim());
        setResults(found);
      } catch (err) {
        setError((err as Error).message);
      }
    }, 180);
    return () => clearTimeout(handle);
  }, [query, open]);

  const handleRequest = async (userId: string) => {
    setBusy(true);
    setError(null);
    try {
      await thoughtApi.requestFriend(userId);
      await refresh();
      onFriendsChanged?.();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const handleAccept = async (userId: string) => {
    setBusy(true);
    try {
      await thoughtApi.acceptFriend(userId);
      await refresh();
      onFriendsChanged?.();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const handleDecline = async (userId: string) => {
    setBusy(true);
    try {
      await thoughtApi.declineFriend(userId);
      await refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <div className={`drawer-backdrop ${open ? "visible" : ""}`} onClick={onClose} />
      <aside className={`drawer ${open ? "open" : ""}`}>
        <div className="drawer-header">
          <div className="drawer-title">friends</div>
          <button className="drawer-close" onClick={onClose}>
            ×
          </button>
        </div>

        <div className="drawer-section">
          <div className="drawer-label">find</div>
          <input
            className="drawer-input"
            placeholder="search by display name"
            value={query}
            onChange={(e) => setQuery(e.currentTarget.value)}
          />
          {results.length > 0 ? (
            <ul className="drawer-list">
              {results.map((r) => (
                <li key={r.id} className="drawer-item">
                  <button
                    className="drawer-item-main drawer-item-main-button"
                    onClick={() => onOpenProfile?.(r.id)}
                    disabled={!onOpenProfile}
                  >
                    <div className="drawer-item-name">{r.display_name}</div>
                    {r.top_clusters.length > 0 ? (
                      <div className="drawer-item-sub">{r.top_clusters.join(" · ")}</div>
                    ) : null}
                  </button>
                  <button
                    className="drawer-action"
                    disabled={busy}
                    onClick={() => handleRequest(r.id)}
                  >
                    connect
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
        </div>

        {suggestions.length > 0 ? (
          <div className="drawer-section">
            <div className="drawer-label">people you may know</div>
            <ul className="drawer-list">
              {suggestions.slice(0, 8).map((s) => (
                <li key={s.id} className="drawer-item">
                  <button
                    className="drawer-item-main drawer-item-main-button"
                    onClick={() => onOpenProfile?.(s.id)}
                    disabled={!onOpenProfile}
                  >
                    <div className="drawer-item-name">{s.display_name}</div>
                    {s.top_clusters.length > 0 ? (
                      <div className="drawer-item-sub">{s.top_clusters.join(" · ")}</div>
                    ) : null}
                  </button>
                  <button
                    className="drawer-action"
                    disabled={busy}
                    onClick={() => handleRequest(s.id)}
                  >
                    connect
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {data?.incoming.length ? (
          <div className="drawer-section">
            <div className="drawer-label">incoming</div>
            <ul className="drawer-list">
              {data.incoming.map((f) => (
                <li key={f.id} className="drawer-item">
                  <button
                    className="drawer-item-main drawer-item-main-button"
                    onClick={() => onOpenProfile?.(f.id)}
                    disabled={!onOpenProfile}
                  >
                    <div className="drawer-item-name">{f.display_name}</div>
                    {f.top_clusters.length > 0 ? (
                      <div className="drawer-item-sub">{f.top_clusters.join(" · ")}</div>
                    ) : null}
                  </button>
                  <div className="drawer-actions">
                    <button className="drawer-action" disabled={busy} onClick={() => handleAccept(f.id)}>
                      accept
                    </button>
                    <button
                      className="drawer-action drawer-action-muted"
                      disabled={busy}
                      onClick={() => handleDecline(f.id)}
                    >
                      decline
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        <div className="drawer-section">
          <div className="drawer-label">connected</div>
          {data?.friends.length ? (
            <ul className="drawer-list">
              {data.friends.map((f) => (
                <li key={f.id} className="drawer-item">
                  <button
                    className="drawer-item-main drawer-item-main-button"
                    onClick={() => onOpenProfile?.(f.id)}
                    disabled={!onOpenProfile}
                  >
                    <div className="drawer-item-name">{f.display_name}</div>
                    <div className="drawer-item-meta">
                      {f.resonance_score !== undefined && f.resonance_score !== null ? (
                        <span className="drawer-badge">{f.resonance_score}</span>
                      ) : null}
                      {f.top_clusters.length > 0 ? (
                        <div className="drawer-item-sub">{f.top_clusters.join(" · ")}</div>
                      ) : null}
                    </div>
                    {f.shared_topics && f.shared_topics.length > 0 ? (
                      <div className="drawer-item-sub">shared: {f.shared_topics.join(" · ")}</div>
                    ) : null}
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <div className="drawer-empty">no friends yet — search above to connect.</div>
          )}
        </div>

        {data?.outgoing.length ? (
          <div className="drawer-section">
            <div className="drawer-label">pending</div>
            <ul className="drawer-list">
              {data.outgoing.map((f) => (
                <li key={f.id} className="drawer-item">
                  <button
                    className="drawer-item-main drawer-item-main-button"
                    onClick={() => onOpenProfile?.(f.id)}
                    disabled={!onOpenProfile}
                  >
                    <div className="drawer-item-name">{f.display_name}</div>
                    <div className="drawer-item-sub">awaiting response</div>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {error ? <div className="drawer-error">{error}</div> : null}
      </aside>
    </>
  );
}
