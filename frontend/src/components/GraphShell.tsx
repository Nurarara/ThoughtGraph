import {
  FormEvent,
  useDeferredValue,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { ArrowRightIcon } from "@phosphor-icons/react/ArrowRight";
import { CompassIcon } from "@phosphor-icons/react/Compass";
import { DotsThreeIcon } from "@phosphor-icons/react/DotsThree";
import { MagnifyingGlassIcon } from "@phosphor-icons/react/MagnifyingGlass";
import { PaperPlaneTiltIcon } from "@phosphor-icons/react/PaperPlaneTilt";
import { PlanetIcon } from "@phosphor-icons/react/Planet";
import { PlayIcon } from "@phosphor-icons/react/Play";
import { PlusIcon } from "@phosphor-icons/react/Plus";
import { QuotesIcon } from "@phosphor-icons/react/Quotes";
import { SignOutIcon } from "@phosphor-icons/react/SignOut";
import { SparkleIcon } from "@phosphor-icons/react/Sparkle";
import { UserCircleIcon } from "@phosphor-icons/react/UserCircle";
import { UsersThreeIcon } from "@phosphor-icons/react/UsersThree";
import { XIcon } from "@phosphor-icons/react/X";

import { GraphCanvas } from "./GraphCanvas";
import { LandingOrbitField } from "./landing/LandingOrbitField";
import { LaterPhaseCommandCenter } from "./phase/LaterPhaseSurfaces";
import {
  clearSession,
  graphApi,
  loadSession,
  resolveMediaUrl,
  saveSession,
  type AdjacentPeopleResponse,
  type DiscoveryExploreFilters,
  type DiscoveryExploreResponse,
  type DiscoveryFilterAvailability,
  type DiscoveryNodeItem,
  type DiscoveryPersonItem,
  type FriendListItem,
  type FriendsResponse,
  type GraphClusterRecord,
  type GraphNativeResponse,
  type GraphNodeRecord,
  type GraphSearchResult,
  type GraphViewport,
  type MeRead,
  type MeUpdateRequest,
  type MediaAssetRead,
  type NodeCreateRequest,
  type NodeRead,
  type NodeThreadResponse,
  type RelatedIdeasResponse,
  type RestrictionUpdate,
  type SessionPayload,
  type SocialNeighborhoodItem,
  type SocialNeighborhoodResponse,
  type SocialProfileRead,
  type SocialRelationshipRead,
  type SocialSearchResult,
  type UploadProgress,
} from "../lib/apiClient";
import { nodeDisplayLabel } from "../lib/nodeDisplay";
import { canReuseUploadedAsset, resolveComposerVisibility } from "../lib/composerDecisions";

const DEFAULT_VIEWPORT: GraphViewport = {
  center_x: 0,
  center_y: 0,
  zoom_hint: 1,
};

const STARTER_THOUGHTS: Array<{
  title: string;
  content_text: string;
  visibility: NodeCreateRequest["visibility"];
}> = [
  {
    title: "What I am building",
    content_text: "I am building ThoughtGraph as a graph-native social product where ideas are explored spatially instead of through a feed.",
    visibility: "private",
  },
  {
    title: "What I am questioning",
    content_text: "I want to map the questions I keep returning to so I can see how they connect over time.",
    visibility: "private",
  },
  {
    title: "What is shaping me",
    content_text: "These are the people, topics, and sources influencing how I think right now.",
    visibility: "friends",
  },
];

function relativeTime(iso: string | null | undefined) {
  if (!iso) return "unknown";
  const diff = Date.now() - new Date(iso).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function initials(name: string | null | undefined) {
  const value = name?.trim() ?? "";
  return value ? value[0].toUpperCase() : "T";
}

function relationshipLabel(relationship: SocialRelationshipRead | null | undefined) {
  if (!relationship) return "unknown";
  if (relationship.blocked_by_target) return "blocked by target";
  if (relationship.blocked) return "blocked";
  if (relationship.restricted_by_target) return "restricted by target";
  if (relationship.restricted) return "restricted";
  if (relationship.friendship_state === "accepted") return "friend";
  if (relationship.friendship_state === "incoming") return "incoming request";
  if (relationship.friendship_state === "outgoing") return "request sent";
  if (relationship.following && relationship.followed_by) return "mutual";
  if (relationship.following) return "following";
  if (relationship.followed_by) return "followed by";
  return "not connected";
}

function visibilityOptions() {
  return ["private", "friends", "public"] as const;
}

function focusViewportFor(node: GraphNodeRecord, viewport: GraphViewport): GraphViewport {
  const zoom =
    node.kind === "image" ? 1.22 : node.kind === "video" ? 1.2 : node.kind === "link" ? 1.16 : 1.26;
  return {
    center_x: node.x,
    center_y: node.y,
    zoom_hint: Math.max(Math.min(viewport.zoom_hint, 1.35), zoom),
  };
}

function fallbackNodeRead(node: GraphNodeRecord): NodeRead {
  return {
    ...node,
    metadata_json: {},
  };
}

function formatBytes(value: number | null | undefined) {
  if (!value || value < 1) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let size = value;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }
  const digits = size >= 10 || unitIndex === 0 ? 0 : 1;
  return `${size.toFixed(digits)} ${units[unitIndex]}`;
}

function mediaStatusLabel(status: string | null | undefined) {
  if (!status) return "no media";
  if (status === "awaiting_upload") return "awaiting upload";
  if (status === "uploaded") return "uploaded";
  if (status === "processing") return "processing";
  if (status === "ready") return "ready";
  if (status === "failed") return "failed";
  return status.replaceAll("_", " ");
}

function mediaStatusTone(status: string | null | undefined) {
  if (status === "ready") return "ready";
  if (status === "failed") return "failed";
  if (status === "processing" || status === "uploaded" || status === "awaiting_upload") return "processing";
  return "neutral";
}

function discoveryReasonLabel(reason: string) {
  if (reason === "semantic_overlap") return "semantic overlap";
  if (reason === "social_proximity") return "social proximity";
  if (reason === "novelty") return "novelty";
  if (reason === "outside_bubble") return "outside your bubble";
  if (reason === "shared_topics") return "shared topics";
  if (reason === "public_adjacency") return "public adjacency";
  return reason.replaceAll("_", " ");
}

function discoveryFilterLabel(key: keyof DiscoveryExploreFilters) {
  if (key === "close_to_me") return "close to me";
  if (key === "outside_my_bubble") return "outside my bubble";
  if (key === "high_evidence") return "high evidence";
  if (key === "new_low_spread") return "new and low-spread";
  if (key === "trusted_only") return "trusted only";
  return key.replaceAll("_", " ");
}

function formatDiscoveryScore(value: number) {
  return `${Math.round(value * 100)}%`;
}

function mediaPosterUrl(node: Pick<NodeRead, "thumbnail_url" | "media_url"> | Pick<GraphNodeRecord, "thumbnail_url" | "media_url">, asset?: MediaAssetRead | null) {
  return resolveMediaUrl(asset?.thumbnail_url ?? asset?.original_url ?? node.thumbnail_url ?? node.media_url);
}

function mediaPlaybackUrl(node: Pick<NodeRead, "playback_url" | "media_url"> | Pick<GraphNodeRecord, "playback_url" | "media_url">, asset?: MediaAssetRead | null) {
  return resolveMediaUrl(asset?.playback_url ?? asset?.original_url ?? node.playback_url ?? node.media_url);
}

function graphBounds(graph: GraphNativeResponse | null) {
  if (!graph || graph.nodes.length === 0) {
    return { minX: -400, maxX: 400, minY: -300, maxY: 300 };
  }

  const xs = graph.nodes.map((node) => node.x);
  const ys = graph.nodes.map((node) => node.y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const padX = Math.max(160, (maxX - minX) * 0.18);
  const padY = Math.max(120, (maxY - minY) * 0.18);

  return {
    minX: minX - padX,
    maxX: maxX + padX,
    minY: minY - padY,
    maxY: maxY + padY,
  };
}

function NodeChip({
  node,
  onFocus,
}: {
  node: GraphNodeRecord;
  onFocus: (nodeId: string) => void;
}) {
  return (
    <button className="node-chip" onClick={() => onFocus(node.id)} type="button">
      <span className="node-chip-dot" style={{ background: node.cluster_color ?? "#9aa4c0" }} />
      <span className="node-chip-title">{nodeDisplayLabel(node, 48)}</span>
      <span className="node-chip-meta">{node.kind}</span>
    </button>
  );
}

function MiniMap({
  graph,
  viewport,
  onJump,
}: {
  graph: GraphNativeResponse | null;
  viewport: GraphViewport;
  onJump: (next: GraphViewport) => void;
}) {
  const bounds = graphBounds(graph);
  const width = 180;
  const height = 120;
  const scaleX = width / (bounds.maxX - bounds.minX || 1);
  const scaleY = height / (bounds.maxY - bounds.minY || 1);
  const scale = Math.min(scaleX, scaleY);

  return (
    <div className="minimap">
      <div className="minimap-label">minimap</div>
      <svg viewBox={`0 0 ${width} ${height}`} className="minimap-svg">
        <rect x="0" y="0" width={width} height={height} rx="18" fill="rgba(255,255,255,0.03)" />
        <rect
          x={(viewport.center_x - 70 - bounds.minX) * scale}
          y={(viewport.center_y - 50 - bounds.minY) * scale}
          width={140 * scale}
          height={100 * scale}
          rx="10"
          fill="none"
          stroke="rgba(255,255,255,0.7)"
          strokeWidth="1.5"
        />
        {graph?.nodes.map((node) => (
          <circle
            key={node.id}
            cx={(node.x - bounds.minX) * scale}
            cy={(node.y - bounds.minY) * scale}
            r={Math.max(1.5, Math.min(4, node.connection_count / 2 + 1.5))}
            fill={node.cluster_color ?? "#c0cadf"}
            opacity="0.7"
            onClick={() =>
              onJump({
                center_x: node.x,
                center_y: node.y,
                zoom_hint: Math.max(1.4, viewport.zoom_hint),
              })
            }
          />
        ))}
      </svg>
    </div>
  );
}

function SearchPanel({
  open,
  query,
  results,
  loading,
  onClose,
  onQueryChange,
  onFocus,
}: {
  open: boolean;
  query: string;
  results: GraphSearchResult[];
  loading: boolean;
  onClose: () => void;
  onQueryChange: (value: string) => void;
  onFocus: (nodeId: string) => void;
}) {
  if (!open) return null;

  return (
    <div className="sheet-backdrop visible" onClick={onClose}>
      <section className="search-panel" onClick={(event) => event.stopPropagation()}>
        <div className="search-panel-head">
          <div>
            <div className="drawer-label">search to focus</div>
            <h2>Command graph</h2>
          </div>
          <button className="sheet-close" onClick={onClose} type="button">
            x
          </button>
        </div>
        <input
          autoFocus
          className="search-input"
          placeholder="search nodes, titles, topics"
          value={query}
          onChange={(event) => onQueryChange(event.currentTarget.value)}
        />
        <div className="search-results">
          {loading ? <div className="drawer-empty">searching...</div> : null}
          {!loading && results.length === 0 && query.trim() ? (
            <div className="drawer-empty">no matching nodes</div>
          ) : null}
          {results.map((item) => (
            <button
              key={item.node_id}
              className="search-result"
              onClick={() => onFocus(item.node_id)}
              type="button"
            >
              <span className="search-result-color" style={{ background: item.cluster_color ?? "#9aa4c0" }} />
              <span className="search-result-main">
                <strong>{nodeDisplayLabel(item, 56)}</strong>
                <span>{item.preview_text ?? "no preview"}</span>
              </span>
              <span className="search-result-meta">
                <em>{item.cluster_label ?? "ungrouped"}</em>
                <strong>{Math.round(item.score)}</strong>
              </span>
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}

function EmptyGraphPrompt({
  visible,
  onStart,
}: {
  visible: boolean;
  onStart: (starter?: (typeof STARTER_THOUGHTS)[number]) => void;
}) {
  if (!visible) return null;

  return (
    <section className="empty-graph-card">
      <div className="drawer-label">first graph</div>
      <h2>Add more thoughts to build your graph</h2>
      <p>
        Your graph is still empty. Start with a few simple posts so ThoughtGraph can form your first cluster
        and give the canvas some shape.
      </p>
      <div className="empty-graph-actions">
        <button className="drawer-action" type="button" onClick={() => onStart()}>
          write from scratch
        </button>
      </div>
      <div className="empty-graph-grid">
        {STARTER_THOUGHTS.map((starter) => (
          <button
            key={starter.title}
            className="empty-graph-starter"
            type="button"
            onClick={() => onStart(starter)}
          >
            <strong>{starter.title}</strong>
            <span>{starter.content_text}</span>
          </button>
        ))}
      </div>
    </section>
  );
}

function NodeComposer({
  open,
  contextNode,
  draft,
  onClose,
  onCreate,
  onBusyChange,
}: {
  open: boolean;
  contextNode: NodeRead | null;
  draft: Partial<NodeCreateRequest> | null;
  onClose: () => void;
  onCreate: (payload: NodeCreateRequest) => Promise<void>;
  onBusyChange: (busy: boolean) => void;
}) {
  const [kind, setKind] = useState<NodeCreateRequest["kind"]>("thought");
  const [title, setTitle] = useState("");
  const [contentText, setContentText] = useState("");
  const [visibility, setVisibility] = useState<NodeCreateRequest["visibility"]>("private");
  const [linkUrl, setLinkUrl] = useState("");
  const [externalMediaUrl, setExternalMediaUrl] = useState("");
  const [replyToNodeId, setReplyToNodeId] = useState<string | null>(null);
  const [quoteOfNodeId, setQuoteOfNodeId] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [assetDraft, setAssetDraft] = useState<MediaAssetRead | null>(null);
  const [uploadProgress, setUploadProgress] = useState<UploadProgress | null>(null);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    setError(null);
    setUploadStatus(null);
    setUploadProgress(null);
    setAssetDraft(null);
    setKind(draft?.kind ?? "thought");
    setTitle(draft?.title ?? "");
    setContentText(draft?.content_text ?? "");
    setVisibility(resolveComposerVisibility(draft?.visibility, contextNode?.visibility));
    setLinkUrl(draft?.link_url ?? "");
    setExternalMediaUrl(draft?.media?.url ?? "");
    setSelectedFile(null);
    setReplyToNodeId(draft?.reply_to_node_id ?? null);
    setQuoteOfNodeId(draft?.quote_of_node_id ?? null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }, [contextNode, draft, open]);

  useEffect(() => {
    if (kind !== "image" && kind !== "video") {
      setSelectedFile(null);
      setAssetDraft(null);
      setUploadProgress(null);
      setUploadStatus(null);
    }
  }, [kind]);

  if (!open) return null;

  const handleFileChange = (file: File | null) => {
    setSelectedFile(file);
    setAssetDraft(null);
    setUploadProgress(null);
    setUploadStatus(file ? `ready to upload ${file.name}` : null);
    if (!file) return;
    if (file.type.startsWith("video/")) {
      setKind("video");
    } else if (file.type.startsWith("image/")) {
      setKind("image");
    }
  };

  const handleKindChange = (nextKind: NodeCreateRequest["kind"]) => {
    if (busy || nextKind === kind) return;
    setKind(nextKind);
    setSelectedFile(null);
    setAssetDraft(null);
    setUploadProgress(null);
    setUploadStatus(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    onBusyChange(true);
    setError(null);
    try {
      const payload: NodeCreateRequest = {
        kind,
        visibility,
      };
      let uploadedAsset: MediaAssetRead | null = null;

      if (title.trim()) payload.title = title.trim();
      if (contentText.trim()) payload.content_text = contentText.trim();
      if (kind === "link" && linkUrl.trim()) payload.link_url = linkUrl.trim();
      if (kind === "image" || kind === "video") {
        if (!selectedFile && !externalMediaUrl.trim()) {
          throw new Error(`Add a ${kind} file or external media URL before publishing.`);
        }
        const reusableAsset = assetDraft && canReuseUploadedAsset(assetDraft, kind) ? assetDraft : null;
        if (selectedFile && reusableAsset) {
          uploadedAsset = reusableAsset;
          setUploadStatus(`reusing ${mediaStatusLabel(reusableAsset.status)} upload`);
          payload.media = {
            asset_id: reusableAsset.id,
            filename: reusableAsset.filename ?? selectedFile.name,
            mime_type: reusableAsset.mime_type ?? selectedFile.type,
            size_bytes: reusableAsset.size_bytes ?? selectedFile.size,
            width: reusableAsset.width ?? undefined,
            height: reusableAsset.height ?? undefined,
          };
        } else if (selectedFile) {
          const mimeType =
            selectedFile.type || (kind === "video" ? "video/mp4" : "image/jpeg");
          setUploadStatus("preparing upload");
          const created = await graphApi.createMediaUpload({
            kind: kind === "video" ? "video" : "image",
            filename: selectedFile.name,
            mime_type: mimeType,
            size_bytes: selectedFile.size,
          });
          setAssetDraft(created.asset);
          setUploadStatus("uploading");
          uploadedAsset = await graphApi.uploadMediaContent(created.upload, selectedFile, (progress) => {
            setUploadProgress(progress);
          });
          setAssetDraft(uploadedAsset);
          setUploadStatus(mediaStatusLabel(uploadedAsset.status));
          payload.media = {
            asset_id: uploadedAsset.id,
            filename: uploadedAsset.filename ?? selectedFile.name,
            mime_type: uploadedAsset.mime_type ?? mimeType,
            size_bytes: uploadedAsset.size_bytes ?? selectedFile.size,
            width: uploadedAsset.width ?? undefined,
            height: uploadedAsset.height ?? undefined,
          };
        } else if (externalMediaUrl.trim()) {
          payload.media = {
            url: externalMediaUrl.trim(),
          };
        }
      }
      if (replyToNodeId) payload.reply_to_node_id = replyToNodeId;
      if (quoteOfNodeId) payload.quote_of_node_id = quoteOfNodeId;

      await onCreate(payload);
      setTitle("");
      setContentText("");
      setLinkUrl("");
      setExternalMediaUrl("");
      setSelectedFile(null);
      setAssetDraft(null);
      setUploadProgress(null);
      setUploadStatus(uploadedAsset ? `published with ${mediaStatusLabel(uploadedAsset.status)}` : null);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create node.");
    } finally {
      setBusy(false);
      onBusyChange(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={busy ? undefined : onClose}>
      <section className="composer-card" onClick={(event) => event.stopPropagation()}>
        <div className="modal-title">new node</div>
        {contextNode ? (
          <div className="composer-context">
            <div className="drawer-label">context</div>
            <div className="composer-context-title">{nodeDisplayLabel(contextNode, 72)}</div>
            <div className="drawer-copy">{contextNode.preview_text ?? contextNode.content_text ?? "No preview."}</div>
          </div>
        ) : null}
        <form className="composer-form" onSubmit={handleSubmit}>
          <div className="composer-row">
            {(["thought", "image", "video", "link"] as const).map((item) => (
              <button
                key={item}
                type="button"
                className={`composer-kind ${kind === item ? "selected" : ""}`}
                onClick={() => handleKindChange(item)}
                disabled={busy}
              >
                {item}
              </button>
            ))}
          </div>
          <label className="modal-field">
            <span className="modal-label">title</span>
            <input className="modal-input" value={title} onChange={(event) => setTitle(event.currentTarget.value)} />
          </label>
          <label className="modal-field">
            <span className="modal-label">content</span>
            <textarea
              className="modal-textarea"
              rows={5}
              value={contentText}
              onChange={(event) => setContentText(event.currentTarget.value)}
              placeholder="thoughts, annotations, notes"
            />
          </label>
          {kind === "link" ? (
            <label className="modal-field">
              <span className="modal-label">link url</span>
              <input className="modal-input" value={linkUrl} onChange={(event) => setLinkUrl(event.currentTarget.value)} />
            </label>
          ) : null}
          {kind === "image" || kind === "video" ? (
            <>
              <label className="modal-field">
                <span className="modal-label">{kind} file</span>
                <input
                  ref={fileInputRef}
                  className="modal-input file-input"
                  type="file"
                  accept={kind === "video" ? "video/*" : "image/*"}
                  onChange={(event) => handleFileChange(event.currentTarget.files?.[0] ?? null)}
                />
              </label>
              <label className="modal-field">
                <span className="modal-label">external media url</span>
                <input
                  className="modal-input"
                  value={externalMediaUrl}
                  onChange={(event) => setExternalMediaUrl(event.currentTarget.value)}
                  placeholder="optional fallback for external media"
                />
              </label>
              {selectedFile ? (
                <div className="composer-upload-card">
                  <div className="composer-upload-head">
                    <strong>{selectedFile.name}</strong>
                    <span>{formatBytes(selectedFile.size)}</span>
                  </div>
                  <div className="composer-upload-meta">
                    <span>{selectedFile.type || (kind === "video" ? "video" : "image")}</span>
                    {uploadStatus ? (
                      <span className={`status-pill ${mediaStatusTone(assetDraft?.status ?? uploadStatus)}`}>
                        {uploadStatus}
                      </span>
                    ) : null}
                  </div>
                  {uploadProgress ? (
                    <div className="composer-progress">
                      <div className="composer-progress-bar">
                        <span style={{ width: `${uploadProgress.percent}%` }} />
                      </div>
                      <small>
                        {uploadProgress.percent}% uploaded ({formatBytes(uploadProgress.loaded)} / {formatBytes(uploadProgress.total)})
                      </small>
                    </div>
                  ) : null}
                  {assetDraft?.status && assetDraft.status !== "awaiting_upload" ? (
                    <small className="composer-upload-note">
                      asset {assetDraft.id.slice(0, 8)} is {mediaStatusLabel(assetDraft.status)}
                    </small>
                  ) : null}
                </div>
              ) : (
                <div className="drawer-empty">
                  Select a {kind} file for upload. External URLs still work, but uploaded media is the primary path.
                </div>
              )}
            </>
          ) : null}
          <label className="modal-field">
            <span className="modal-label">visibility</span>
            <select
              className="modal-input"
              value={visibility}
              onChange={(event) => setVisibility(event.currentTarget.value as NodeCreateRequest["visibility"])}
            >
              {visibilityOptions().map((option) => (
                <option value={option} key={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
          <div className="composer-edges">
            <label className="composer-edge">
              <span className="modal-label">reply to</span>
              <input
                className="modal-input"
                value={replyToNodeId ?? ""}
                onChange={(event) => setReplyToNodeId(event.currentTarget.value || null)}
                placeholder="optional node id"
              />
            </label>
            <label className="composer-edge">
              <span className="modal-label">quote of</span>
              <input
                className="modal-input"
                value={quoteOfNodeId ?? ""}
                onChange={(event) => setQuoteOfNodeId(event.currentTarget.value || null)}
                placeholder="optional node id"
              />
            </label>
          </div>
          {kind !== "thought" && kind !== "link" && uploadStatus ? (
            <div className="composer-upload-status">
              <span className={`status-pill ${mediaStatusTone(assetDraft?.status ?? uploadStatus)}`}>
                {uploadStatus}
              </span>
              {assetDraft?.error_message ? <span>{assetDraft.error_message}</span> : null}
            </div>
          ) : null}
          {error ? <div className="modal-error">{error}</div> : null}
          <div className="modal-actions">
            <button className="modal-secondary" type="button" onClick={onClose} disabled={busy}>
              cancel
            </button>
            <button className="modal-submit" type="submit" disabled={busy}>
              {busy ? "saving..." : "create"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

function AuthLanding({
  onAuthenticated,
  notice,
}: {
  onAuthenticated: (session: SessionPayload) => void;
  notice?: string | null;
}) {
  const [email, setEmail] = useState("");
  const [token, setToken] = useState("");
  const [magicLink, setMagicLink] = useState<string | null>(null);
  const [stage, setStage] = useState<"request" | "verify" | "sent">("request");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [authExpanded, setAuthExpanded] = useState(Boolean(notice));
  const [showExplainer, setShowExplainer] = useState(false);
  const verifiedUrlTokenRef = useRef<string | null>(null);

  useEffect(() => {
    const tokenFromUrl = new URL(window.location.href).searchParams.get("token");
    if (!tokenFromUrl) return;
    if (verifiedUrlTokenRef.current === tokenFromUrl) return;
    verifiedUrlTokenRef.current = tokenFromUrl;

    setAuthExpanded(true);
    setStage("verify");
    setToken(tokenFromUrl);
    setBusy(true);
    setError(null);
    void graphApi
      .verifyLink(tokenFromUrl)
      .then((session) => {
        saveSession(session);
        onAuthenticated(session);
        const nextUrl = `${window.location.origin}${window.location.pathname}`;
        window.history.replaceState({}, document.title, nextUrl);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Could not verify token.");
      })
      .finally(() => setBusy(false));
  }, [onAuthenticated]);

  useEffect(() => {
    if (notice) setAuthExpanded(true);
  }, [notice]);

  useEffect(() => {
    if (!authExpanded) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !busy) setAuthExpanded(false);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [authExpanded, busy]);

  const requestLink = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const response = await graphApi.requestLink(email.trim());
      setMagicLink(response.magic_link);
      if (response.magic_link) {
        setStage("verify");
        const tokenFromLink = new URL(response.magic_link).searchParams.get("token");
        setToken(tokenFromLink ?? "");
      } else {
        setStage("sent");
        setToken("");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not request link.");
    } finally {
      setBusy(false);
    }
  };

  const verify = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const session = await graphApi.verifyLink(token.trim());
      saveSession(session);
      onAuthenticated(session);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not verify token.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-shell observatory-landing">
      <LandingOrbitField />
      <header className="landing-header">
        <div className="landing-brand"><PlanetIcon size={18} weight="fill" aria-hidden="true" />ThoughtGraph</div>
        <div className="landing-calibration">private by design&nbsp;&nbsp;/&nbsp;&nbsp;evidence over opinion</div>
      </header>

      <main className="landing-hero">
        <div className="landing-eyebrow">Private spatial intelligence</div>
        <h1><span>See what your</span><span>thinking is becoming.</span></h1>
        <p>Capture ideas. Watch relationships surface. Reflect with evidence—not guesses.</p>
        <div className="landing-actions">
          <button className="landing-primary" type="button" onClick={() => setAuthExpanded(true)}>
            Enter your graph <ArrowRightIcon size={20} weight="bold" aria-hidden="true" />
          </button>
          <button
            className="landing-secondary"
            type="button"
            aria-expanded={showExplainer}
            onClick={() => setShowExplainer((visible) => !visible)}
          >
            <PlayIcon size={16} weight="fill" aria-hidden="true" />
            {showExplainer ? "Hide the model" : "See how it works"}
          </button>
        </div>
      </main>

      <div className="landing-trust" aria-label="ThoughtGraph principles">
        <span>Private by design</span>
        <span>Your thoughts stay yours</span>
        <span>Evidence over opinion</span>
      </div>

      {showExplainer ? (
        <section className="landing-explainer" aria-label="How ThoughtGraph works">
          <div><span>01</span><strong>Capture</strong><p>Save the thought before it disappears.</p></div>
          <div><span>02</span><strong>Connect</strong><p>Related ideas move into view as the graph grows.</p></div>
          <div><span>03</span><strong>Reflect</strong><p>See change through traceable evidence, never personality guesses.</p></div>
        </section>
      ) : null}

      {authExpanded ? (
        <>
        <div className="auth-panel-backdrop" aria-hidden="true" onClick={() => { if (!busy) setAuthExpanded(false); }} />
        <section className="auth-card observatory-auth-panel" role="dialog" aria-modal="true" aria-labelledby="auth-title">
          <div className="auth-panel-head">
            <div>
              <div className="drawer-label">Secure entry</div>
              <h2 id="auth-title">
                {stage === "request" ? "Enter your graph" : stage === "verify" ? "Your private link is ready" : "Check your inbox"}
              </h2>
            </div>
            <button className="instrument-icon-button" type="button" aria-label="Close sign in" disabled={busy} onClick={() => setAuthExpanded(false)}>
              <XIcon size={18} aria-hidden="true" />
            </button>
          </div>
          <p className="drawer-copy">
            {stage === "request"
              ? "We will send a single-use link. No password, no public profile by default."
              : stage === "verify"
                ? "Open the secure link, or verify the prepared token here."
                : "Open the link in your email. ThoughtGraph will finish sign-in automatically."}
          </p>
          {notice ? <div className="drawer-empty" role="status">{notice}</div> : null}
          {stage === "request" ? (
            <form className="auth-form" onSubmit={requestLink}>
              <label className="auth-field">
                <span>Email address</span>
                <input
                  autoFocus
                  className="auth-input"
                  type="email"
                  inputMode="email"
                  autoComplete="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(event) => setEmail(event.currentTarget.value)}
                  required
                />
              </label>
              <button className="auth-submit" type="submit" disabled={busy}>
                <PaperPlaneTiltIcon size={18} aria-hidden="true" />
                {busy ? "Sending secure link…" : "Send secure link"}
              </button>
            </form>
          ) : stage === "verify" ? (
            <form className="auth-form" onSubmit={verify}>
              {magicLink ? (
                <a className="auth-link" href={magicLink} target="_blank" rel="noreferrer">
                  Open secure sign-in link <ArrowRightIcon size={16} aria-hidden="true" />
                </a>
              ) : null}
              <label className="auth-field">
                <span>One-time token</span>
                <input
                  autoFocus
                  className="auth-input"
                  type="text"
                  autoComplete="one-time-code"
                  placeholder="Paste token"
                  value={token}
                  onChange={(event) => setToken(event.currentTarget.value)}
                  required
                />
              </label>
              <button className="auth-submit" type="submit" disabled={busy}>
                {busy ? "Verifying…" : "Enter ThoughtGraph"} <ArrowRightIcon size={18} aria-hidden="true" />
              </button>
              <button className="auth-secondary" type="button" onClick={() => {
                setStage("request");
                setToken("");
                setMagicLink(null);
              }}>
                Use a different email
              </button>
            </form>
          ) : (
            <div className="auth-form">
              <div className="drawer-empty" role="status">
                A sign-in link was sent to <strong>{email}</strong>.
              </div>
              <button className="auth-secondary" type="button" onClick={() => {
                setStage("request");
                setToken("");
                setMagicLink(null);
              }}>
                Use a different email
              </button>
            </div>
          )}
          {error ? <div className="auth-error" role="alert">{error}</div> : null}
        </section>
        </>
      ) : null}
    </div>
  );
}

function GraphHeader({
  session,
  me,
  graph,
  socialMode,
  syncing,
  onOpenDiscovery,
  onOpenSystems,
  onToggleSocialMode,
  onOpenComposer,
  onOpenProfile,
  onOpenPeople,
  onOpenSearch,
  onLogout,
  onReturnToSelf,
  onJumpToNode,
  trail,
}: {
  session: SessionPayload;
  me: MeRead | null;
  graph: GraphNativeResponse | null;
  socialMode: boolean;
  syncing: boolean;
  onOpenDiscovery: () => void;
  onOpenSystems: () => void;
  onToggleSocialMode: () => void;
  onOpenComposer: () => void;
  onOpenProfile: () => void;
  onOpenPeople: () => void;
  onOpenSearch: () => void;
  onLogout: () => void;
  onReturnToSelf: () => void;
  onJumpToNode: (nodeId: string) => void;
  trail: GraphNodeRecord[];
}) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [moreMenuOpen, setMoreMenuOpen] = useState(false);
  const runMenuAction = (action: () => void) => {
    setMobileMenuOpen(false);
    setMoreMenuOpen(false);
    action();
  };

  useEffect(() => {
    if (!mobileMenuOpen && !moreMenuOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setMobileMenuOpen(false);
        setMoreMenuOpen(false);
      }
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [mobileMenuOpen, moreMenuOpen]);

  return (
    <header className={`graph-header ${mobileMenuOpen ? "menu-open" : ""}`}>
      <div className="graph-brand">
        <div className="graph-brand-mark"><PlanetIcon size={16} weight="fill" aria-hidden="true" />ThoughtGraph</div>
        <div className="graph-location">
          <button type="button" onClick={onReturnToSelf}>Personal graph</button>
          <span aria-hidden="true">/</span>
          <span>{trail.length ? nodeDisplayLabel(trail[trail.length - 1], 32) : "All thoughts"}</span>
        </div>
        <div className={`graph-sync-state ${syncing ? "is-syncing" : ""}`}>{syncing ? "recalibrating" : `${graph?.nodes.length ?? 0} nodes in field`}</div>
      </div>
      <button
        className="mobile-nav-toggle"
        type="button"
        aria-label={mobileMenuOpen ? "Close navigation menu" : "Open navigation menu"}
        aria-expanded={mobileMenuOpen}
        aria-controls="graph-primary-actions"
        onClick={() => setMobileMenuOpen((open) => !open)}
      >
        {mobileMenuOpen ? <XIcon size={20} aria-hidden="true" /> : <DotsThreeIcon size={22} weight="bold" aria-hidden="true" />}
      </button>
      <div className="graph-trail">
        {trail.slice(-3).map((node) => (
          <NodeChip key={node.id} node={node} onFocus={onJumpToNode} />
        ))}
      </div>
      <div className="graph-actions" id="graph-primary-actions">
        <button className="topbar-button" onClick={() => runMenuAction(onOpenSearch)} type="button">
          <MagnifyingGlassIcon size={18} aria-hidden="true" /> <span>Search</span>
        </button>
        <button className="topbar-button" onClick={() => runMenuAction(onOpenDiscovery)} type="button">
          <CompassIcon size={18} aria-hidden="true" /> <span>Explore</span>
        </button>
        <button className="topbar-button capture" onClick={() => runMenuAction(onOpenComposer)} type="button">
          <PlusIcon size={18} weight="bold" aria-hidden="true" /> <span>Capture</span>
        </button>
        <button className="topbar-button account" aria-label="Open profile" onClick={() => runMenuAction(onOpenProfile)} type="button">
          <UserCircleIcon size={22} aria-hidden="true" /><span>{initials(me?.display_name ?? session.display_name)}</span>
        </button>
        <div className="graph-more-wrap">
          <button className="topbar-button more" type="button" aria-label="More workspace actions" aria-expanded={moreMenuOpen} onClick={() => setMoreMenuOpen((open) => !open)}>
            <DotsThreeIcon size={22} weight="bold" aria-hidden="true" />
          </button>
          {moreMenuOpen ? (
            <div className="graph-more-menu">
              <button type="button" onClick={() => runMenuAction(onToggleSocialMode)}>
                <SparkleIcon size={17} aria-hidden="true" /><span>{socialMode ? "Leave social field" : "Enter social field"}</span>
              </button>
              <button type="button" onClick={() => runMenuAction(onOpenPeople)}>
                <UsersThreeIcon size={17} aria-hidden="true" /><span>People</span>
              </button>
              <button type="button" onClick={() => runMenuAction(onOpenSystems)}>
                <PlanetIcon size={17} aria-hidden="true" /><span>Systems & reflections</span>
              </button>
              <button type="button" onClick={() => runMenuAction(onLogout)}>
                <SignOutIcon size={17} aria-hidden="true" /><span>Sign out</span>
              </button>
            </div>
          ) : null}
        </div>
      </div>
    </header>
  );
}

function DiscoveryDrawer({
  open,
  query,
  filters,
  availability,
  explore,
  adjacent,
  loading,
  peopleLoading,
  error,
  onClose,
  onQueryChange,
  onToggleFilter,
  onOpenNode,
  onOpenProfile,
}: {
  open: boolean;
  query: string;
  filters: DiscoveryExploreFilters;
  availability: DiscoveryFilterAvailability | null;
  explore: DiscoveryExploreResponse | null;
  adjacent: AdjacentPeopleResponse | null;
  loading: boolean;
  peopleLoading: boolean;
  error: string | null;
  onClose: () => void;
  onQueryChange: (value: string) => void;
  onToggleFilter: (key: keyof DiscoveryExploreFilters) => void;
  onOpenNode: (node: DiscoveryNodeItem["node"]) => void;
  onOpenProfile: (userId: string) => void;
}) {
  if (!open) return null;

  const filterKeys: Array<keyof DiscoveryExploreFilters> = [
    "close_to_me",
    "outside_my_bubble",
    "high_evidence",
    "new_low_spread",
    "trusted_only",
  ];

  const filterEnabled = (key: keyof DiscoveryFilterAvailability) => availability?.[key] ?? true;

  return (
    <>
      <div className="drawer-backdrop visible" onClick={onClose} />
      <aside className="drawer discovery-drawer open" onClick={(event) => event.stopPropagation()}>
        <div className="drawer-header">
          <div>
            <div className="drawer-label">discovery layer</div>
            <div className="drawer-title">Explainable discovery</div>
          </div>
          <button className="drawer-close" onClick={onClose} type="button">
            x
          </button>
        </div>

        <section className="drawer-section">
          <div className="drawer-label">search and filters</div>
          <input
            className="search-input"
            placeholder="search ideas, topics, claims, sources"
            value={query}
            onChange={(event) => onQueryChange(event.currentTarget.value)}
          />
          <div className="discovery-filter-row">
            {filterKeys.map((key) => {
              const active = Boolean(filters[key]);
              const available = filterEnabled(key as keyof DiscoveryFilterAvailability);
              return (
                <button
                  key={key}
                  type="button"
                  className={`discovery-filter ${active ? "active" : ""} ${!available ? "disabled" : ""}`}
                  disabled={!available}
                  onClick={() => onToggleFilter(key)}
                  title={!available ? "This filter is reserved for a later trust phase." : undefined}
                >
                  {discoveryFilterLabel(key)}
                </button>
              );
            })}
          </div>
          <div className="drawer-copy">
            {explore?.explanation_summary ??
              "Discovery stays explainable: every suggestion includes visible reasons instead of opaque ranking."}
          </div>
        </section>

        <section className="drawer-section">
          <div className="drawer-label">ideas</div>
          {loading ? <div className="drawer-empty">materializing suggestions...</div> : null}
          {!loading && !explore?.items.length ? (
            <div className="drawer-empty">No discovery suggestions yet. Add a few more nodes or broaden your filters.</div>
          ) : null}
          <div className="discovery-list">
            {explore?.items.map((item: DiscoveryNodeItem) => (
              <button
                key={item.node.id}
                type="button"
                className="discovery-card"
                onClick={() => {
                  onOpenNode(item.node);
                  onClose();
                }}
              >
                <div className="discovery-card-head">
                  <div>
                    <strong>{nodeDisplayLabel(item.node, 72)}</strong>
                    <span>{item.node.preview_text ?? item.node.content_text ?? "No preview."}</span>
                  </div>
                  <div className="discovery-score">
                    <small>{discoveryReasonLabel(item.explanation.primary_reason)}</small>
                    <strong>{formatDiscoveryScore(item.explanation.score_breakdown.total)}</strong>
                  </div>
                </div>
                <div className="discovery-card-meta">
                  <span style={{ color: item.node.cluster_color ?? "#9aa4c0" }}>
                    {item.node.cluster_label ?? "Ungrouped"}
                  </span>
                  <span>{item.node.kind}</span>
                  {item.explanation.relationship_to_viewer ? <span>{item.explanation.relationship_to_viewer}</span> : null}
                </div>
                <p className="discovery-summary">Why shown: {item.explanation.summary}</p>
                <div className="discovery-signals">
                  {item.explanation.matched_topics.slice(0, 3).map((topic) => (
                    <span className="topic-chip" key={`${item.node.id}-${topic}`}>
                      {topic}
                    </span>
                  ))}
                  {item.explanation.signal_notes.slice(0, 2).map((note) => (
                    <span className="discovery-note" key={`${item.node.id}-${note}`}>
                      {note}
                    </span>
                  ))}
                </div>
                <div className="discovery-score-row">
                  <span>relevance {formatDiscoveryScore(item.explanation.score_breakdown.relevance)}</span>
                  <span>novelty {formatDiscoveryScore(item.explanation.score_breakdown.novelty)}</span>
                  <span>trust {formatDiscoveryScore(item.explanation.score_breakdown.trust)}</span>
                  <span>social {formatDiscoveryScore(item.explanation.score_breakdown.social_proximity)}</span>
                </div>
              </button>
            ))}
          </div>
        </section>

        <section className="drawer-section">
          <div className="drawer-label">people adjacent to you</div>
          {peopleLoading ? <div className="drawer-empty">mapping nearby people...</div> : null}
          {!peopleLoading && !adjacent?.items.length ? (
            <div className="drawer-empty">No adjacent people yet. Public profiles and shared topics will appear here.</div>
          ) : null}
          <div className="neighborhood-grid">
            {adjacent?.items.map((person: DiscoveryPersonItem) => (
              <button
                key={person.user_id}
                type="button"
                className="neighborhood-card discovery-person-card"
                onClick={() => {
                  onOpenProfile(person.user_id);
                  onClose();
                }}
              >
                <strong>{person.display_name}</strong>
                <span>{person.bio || "No bio shared."}</span>
                <small>Why shown: {person.explanation.summary}</small>
                {person.shared_topics.length ? (
                  <div className="chip-row">
                    {person.shared_topics.slice(0, 3).map((topic) => (
                      <span key={`${person.user_id}-${topic}`} className="topic-chip">
                        {topic}
                      </span>
                    ))}
                  </div>
                ) : null}
                <div className="discovery-score-row">
                  <span>{person.visible_node_count} visible nodes</span>
                  <span>{formatDiscoveryScore(person.explanation.score_breakdown.total)} overlap</span>
                </div>
              </button>
            ))}
          </div>
        </section>

        {error ? <div className="drawer-error">{error}</div> : null}
      </aside>
    </>
  );
}

function SocialDrawer({
  open,
  me,
  query,
  queryResults,
  queryLoading,
  activeProfile,
  activeProfileLoading,
  friends,
  neighborhood,
  onClose,
  onQueryChange,
  onSelectUser,
  onRefreshProfile,
  onToggleFollow,
  onRequestFriend,
  onAcceptFriend,
  onDeclineFriend,
  onRemoveFriend,
  onToggleRestriction,
  busy,
  error,
}: {
  open: boolean;
  me: MeRead | null;
  query: string;
  queryResults: SocialSearchResult[];
  queryLoading: boolean;
  activeProfile: SocialProfileRead | null;
  activeProfileLoading: boolean;
  friends: FriendsResponse | null;
  neighborhood: SocialNeighborhoodResponse | null;
  onClose: () => void;
  onQueryChange: (value: string) => void;
  onSelectUser: (userId: string) => void;
  onRefreshProfile: (userId: string) => void;
  onToggleFollow: (userId: string, following: boolean) => Promise<void>;
  onRequestFriend: (userId: string) => Promise<void>;
  onAcceptFriend: (userId: string) => Promise<void>;
  onDeclineFriend: (userId: string) => Promise<void>;
  onRemoveFriend: (userId: string) => Promise<void>;
  onToggleRestriction: (userId: string, kind: RestrictionUpdate["kind"], active: boolean) => Promise<void>;
  busy: boolean;
  error: string | null;
}) {
  if (!open) return null;

  const renderRelationshipActions = (userId: string, relationship: SocialRelationshipRead) => (
    <div className="relationship-actions">
      <button className="drawer-action" disabled={busy} onClick={() => void onToggleFollow(userId, relationship.following)}>
        {relationship.following ? "unfollow" : "follow"}
      </button>
      {relationship.friendship_state === "incoming" ? (
        <>
          <button className="drawer-action" disabled={busy} onClick={() => void onAcceptFriend(userId)}>
            accept
          </button>
          <button className="drawer-action drawer-action-muted" disabled={busy} onClick={() => void onDeclineFriend(userId)}>
            decline
          </button>
        </>
      ) : null}
      {relationship.friendship_state === "outgoing" ? (
        <button className="drawer-action drawer-action-muted" disabled={busy} onClick={() => void onRemoveFriend(userId)}>
          cancel request
        </button>
      ) : null}
      {relationship.friendship_state === "none" || relationship.friendship_state === "declined" ? (
        <button className="drawer-action" disabled={busy} onClick={() => void onRequestFriend(userId)}>
          request friend
        </button>
      ) : null}
      {relationship.friendship_state === "accepted" ? (
        <button className="drawer-action drawer-action-muted" disabled={busy} onClick={() => void onRemoveFriend(userId)}>
          remove friend
        </button>
      ) : null}
      {(["blocked", "muted", "restricted"] as const).map((kind) => {
        const active = relationship[kind];
        return (
          <button
            key={kind}
            className={`drawer-action ${active ? "drawer-action-active" : "drawer-action-muted"}`}
            disabled={busy}
            onClick={() => void onToggleRestriction(userId, kind, !active)}
            type="button"
          >
            {active ? `un${kind}` : kind}
          </button>
        );
      })}
    </div>
  );

  return (
    <>
      <div className="drawer-backdrop visible" onClick={onClose} />
      <aside className="drawer social-drawer open" onClick={(event) => event.stopPropagation()}>
        <div className="drawer-header">
          <div>
            <div className="drawer-label">social layer</div>
            <div className="drawer-title">people and neighborhood</div>
          </div>
          <button className="drawer-close" onClick={onClose} type="button">
            x
          </button>
        </div>

        <section className="drawer-section">
          <div className="social-summary">
            <div>
              <div className="drawer-label">viewer</div>
              <strong>{me?.display_name ?? "You"}</strong>
            </div>
            <div className="social-stats">
              <span>{me?.follower_count ?? 0} followers</span>
              <span>{me?.following_count ?? 0} following</span>
            </div>
          </div>
        </section>

        <section className="drawer-section">
          <div className="drawer-label">people search</div>
          <input
            className="search-input"
            placeholder="search people by name or bio"
            value={query}
            onChange={(event) => onQueryChange(event.currentTarget.value)}
          />
          <div className="search-results">
            {queryLoading ? <div className="drawer-empty">searching...</div> : null}
            {query.trim() && !queryLoading && queryResults.length === 0 ? (
              <div className="drawer-empty">no matching people</div>
            ) : null}
            {queryResults.map((user) => (
              <button
                key={user.id}
                type="button"
                className="search-result people-result"
                onClick={() => onSelectUser(user.id)}
              >
                <span className="search-result-color" style={{ background: user.relationship.following ? "#7dffe3" : "#94b6ff" }} />
                <span className="search-result-main">
                  <strong>{user.display_name}</strong>
                  <span>{user.bio || "No bio shared."}</span>
                </span>
                <span className="search-result-meta">
                  <em>{relationshipLabel(user.relationship)}</em>
                </span>
              </button>
            ))}
          </div>
        </section>

        <section className="drawer-section">
          <div className="drawer-label">profile</div>
          {activeProfileLoading ? <div className="drawer-empty">loading profile...</div> : null}
          {activeProfile ? (
            <div className="profile-card social-profile-card">
              <div className="social-profile-head">
                <div>
                  <div className="drawer-title">{activeProfile.display_name}</div>
                  <div className="drawer-copy">{activeProfile.bio || "No bio shared."}</div>
                </div>
                <button className="drawer-action" type="button" onClick={() => onRefreshProfile(activeProfile.id)}>
                  refresh
                </button>
              </div>
              <div className="profile-stats">
                <span>{activeProfile.node_count} nodes</span>
                <span>{activeProfile.cluster_count} clusters</span>
                <span>{relativeTime(activeProfile.created_at)}</span>
              </div>
              {activeProfile.top_clusters.length ? (
                <div className="chip-row">
                  {activeProfile.top_clusters.map((cluster) => (
                    <span className="topic-chip" key={cluster}>
                      {cluster}
                    </span>
                  ))}
                </div>
              ) : null}
              <div className="relationship-pill">{relationshipLabel(activeProfile.relationship)}</div>
              {renderRelationshipActions(activeProfile.id, activeProfile.relationship)}
            </div>
          ) : (
            <div className="drawer-empty">Search for a person or click an author chip to inspect their relationship.</div>
          )}
        </section>

        <section className="drawer-section">
          <div className="drawer-label">neighborhood</div>
          <div className="neighborhood-grid">
            {neighborhood?.items.map((item: SocialNeighborhoodItem) => (
              <button
                key={item.user_id}
                type="button"
                className="neighborhood-card"
                onClick={() => onSelectUser(item.user_id)}
              >
                <strong>{item.display_name}</strong>
                <span>{item.visible_node_count} visible nodes</span>
                {item.shared_cluster_labels.length ? (
                  <div className="chip-row">
                    {item.shared_cluster_labels.slice(0, 3).map((cluster) => (
                      <span key={cluster} className="topic-chip">
                        {cluster}
                      </span>
                    ))}
                  </div>
                ) : null}
                {item.shared_topics.length ? <small>{item.shared_topics.join(" · ")}</small> : null}
              </button>
            ))}
            {!neighborhood?.items.length ? <div className="drawer-empty">No nearby social context yet.</div> : null}
          </div>
        </section>

        <section className="drawer-section">
          <div className="drawer-label">friends</div>
          <div className="social-lists">
            <div className="social-list">
              <div className="social-list-title">Friends</div>
              {friends?.friends.length ? (
                friends.friends.map((item: FriendListItem) => (
                  <button key={item.id} className="social-list-row" type="button" onClick={() => onSelectUser(item.id)}>
                    <span>
                      <strong>{item.display_name}</strong>
                      <small>{item.top_clusters.join(" · ") || "General reflection"}</small>
                    </span>
                    <span>{relationshipLabel(item.relationship)}</span>
                  </button>
                ))
              ) : (
                <div className="drawer-empty">No friends yet.</div>
              )}
            </div>
            <div className="social-list">
              <div className="social-list-title">Incoming</div>
              {friends?.incoming.length ? (
                friends.incoming.map((item: FriendListItem) => (
                  <div key={item.id} className="social-list-row">
                    <button type="button" className="social-list-button" onClick={() => onSelectUser(item.id)}>
                      <strong>{item.display_name}</strong>
                      <small>{item.top_clusters.join(" · ") || "General reflection"}</small>
                    </button>
                    <div className="relationship-actions compact">
                      <button className="drawer-action" disabled={busy} onClick={() => void onAcceptFriend(item.id)}>
                        accept
                      </button>
                      <button className="drawer-action drawer-action-muted" disabled={busy} onClick={() => void onDeclineFriend(item.id)}>
                        decline
                      </button>
                    </div>
                  </div>
                ))
              ) : (
                <div className="drawer-empty">No incoming requests.</div>
              )}
            </div>
            <div className="social-list">
              <div className="social-list-title">Outgoing</div>
              {friends?.outgoing.length ? (
                friends.outgoing.map((item: FriendListItem) => (
                  <div key={item.id} className="social-list-row">
                    <button type="button" className="social-list-button" onClick={() => onSelectUser(item.id)}>
                      <strong>{item.display_name}</strong>
                      <small>{item.top_clusters.join(" · ") || "General reflection"}</small>
                    </button>
                    <button className="drawer-action drawer-action-muted" disabled={busy} onClick={() => void onRemoveFriend(item.id)}>
                      remove
                    </button>
                  </div>
                ))
              ) : (
                <div className="drawer-empty">No outgoing requests.</div>
              )}
            </div>
          </div>
        </section>

        {error ? <div className="drawer-error">{error}</div> : null}
      </aside>
    </>
  );
}

function NodeDetailPanel({
  node,
  thread,
  cluster,
  graph,
  onRefreshWorkspace,
  onFocus,
  onOpenProfile,
  onComposeReply,
  onComposeQuote,
  onClose,
}: {
  node: NodeRead | null;
  thread: NodeThreadResponse | null;
  cluster: GraphClusterRecord | null;
  graph: GraphNativeResponse | null;
  onRefreshWorkspace: () => Promise<void>;
  onFocus: (nodeId: string) => void;
  onOpenProfile: (userId: string) => void;
  onComposeReply: () => void;
  onComposeQuote: () => void;
  onClose: () => void;
}) {
  const [mediaAsset, setMediaAsset] = useState<MediaAssetRead | null>(null);
  const [mediaBusy, setMediaBusy] = useState(false);
  const [mediaError, setMediaError] = useState<string | null>(null);
  const [relatedIdeas, setRelatedIdeas] = useState<RelatedIdeasResponse | null>(null);
  const [relatedLoading, setRelatedLoading] = useState(false);
  const [relatedError, setRelatedError] = useState<string | null>(null);

  useEffect(() => {
    if (!node?.media_asset_id) {
      setMediaAsset(null);
      setMediaError(null);
      setMediaBusy(false);
      return;
    }

    setMediaAsset(null);
    let cancelled = false;
    let pollTimeoutId: number | null = null;
    let inFlight = false;
    const isPendingStatus = (status: string | null | undefined) =>
      status === "awaiting_upload" || status === "uploaded" || status === "processing";

    const schedulePoll = (status: string | null | undefined) => {
      if (cancelled || !isPendingStatus(status) || pollTimeoutId !== null) {
        return;
      }
      pollTimeoutId = window.setTimeout(() => {
        pollTimeoutId = null;
        void loadAsset();
      }, 2500);
    };

    const loadAsset = async () => {
      if (cancelled || inFlight) {
        return;
      }
      inFlight = true;
      try {
        const asset = await graphApi.getMediaAsset(node.media_asset_id!);
        if (cancelled) return;
        setMediaAsset(asset);
        setMediaError(null);
        schedulePoll(asset.status);
      } catch (err) {
        if (!cancelled) {
          setMediaError(err instanceof Error ? err.message : "Could not load media state.");
          schedulePoll(node.media_status);
        }
      } finally {
        inFlight = false;
      }
    };

    void loadAsset();

    return () => {
      cancelled = true;
      if (pollTimeoutId !== null) {
        window.clearTimeout(pollTimeoutId);
      }
    };
  }, [node?.media_asset_id, node?.media_status]);

  useEffect(() => {
    if (!node?.id) {
      setRelatedIdeas(null);
      setRelatedError(null);
      setRelatedLoading(false);
      return;
    }

    let cancelled = false;
    setRelatedLoading(true);
    setRelatedError(null);
    void graphApi
      .getRelatedIdeas(node.id, 4)
      .then((response) => {
        if (!cancelled) {
          setRelatedIdeas(response);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setRelatedIdeas(null);
          setRelatedError(err instanceof Error ? err.message : "Could not load related ideas.");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setRelatedLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [node?.id]);

  if (!node) return null;

  const neighbors = graph
    ? graph.edges
        .filter((edge) => edge.source === node.id || edge.target === node.id)
        .map((edge) => (edge.source === node.id ? edge.target : edge.source))
        .filter((value, index, self) => self.indexOf(value) === index)
        .map((id) => graph.nodes.find((item) => item.id === id))
        .filter((item): item is GraphNodeRecord => Boolean(item))
        .slice(0, 6)
    : [];
  const effectiveMediaStatus = mediaAsset?.status ?? node.media_status;
  const imageSource = mediaPosterUrl(node, mediaAsset);
  const videoSource = mediaPlaybackUrl(node, mediaAsset);
  const durationSeconds = mediaAsset?.duration_seconds ?? node.duration_seconds;
  const canRetry = Boolean(node.media_asset_id && effectiveMediaStatus === "failed");

  const handleRetry = async () => {
    if (!node.media_asset_id) return;
    setMediaBusy(true);
    setMediaError(null);
    try {
      const asset = await graphApi.retryMediaAsset(node.media_asset_id);
      setMediaAsset(asset);
      await onRefreshWorkspace();
    } catch (err) {
      setMediaError(err instanceof Error ? err.message : "Could not retry media processing.");
    } finally {
      setMediaBusy(false);
    }
  };

  return (
    <aside className="detail-panel">
      <div className="detail-head">
        <div>
          <div className="detail-classification"><SparkleIcon size={14} weight="fill" aria-hidden="true" />Focused node</div>
          <h2>{nodeDisplayLabel(node, 54)}</h2>
        </div>
        <div className="detail-head-actions">
          <span className="detail-kind">{node.kind}</span>
          <button className="drawer-close detail-close" type="button" aria-label="Close node detail" onClick={onClose}>
            <XIcon size={18} aria-hidden="true" />
          </button>
        </div>
      </div>
      <p className="detail-copy">{node.content_text || node.preview_text || "No body text."}</p>
      <div className="detail-meta">
        <span style={{ color: node.cluster_color ?? cluster?.color ?? "#9aa4c0" }}>
          {node.cluster_label ?? cluster?.label ?? "Ungrouped"}
        </span>
        <span>{node.visibility}</span>
        <span>{relativeTime(node.updated_at)}</span>
        {node.relationship_to_viewer ? <span>{node.relationship_to_viewer}</span> : null}
      </div>
      <div className="detail-actions">
        <button className="drawer-action" type="button" onClick={onComposeReply}>
          <PaperPlaneTiltIcon size={17} aria-hidden="true" />Reply
        </button>
        <button className="drawer-action" type="button" onClick={onComposeQuote}>
          <QuotesIcon size={17} aria-hidden="true" />Quote
        </button>
        {node.author_id ? (
          <button
            className="drawer-action drawer-action-muted"
            type="button"
            onClick={() => node.author_id && onOpenProfile(node.author_id)}
          >
            {node.author_display_name ?? "author"}
          </button>
        ) : null}
      </div>
      {node.topics?.length ? (
        <div className="chip-row">
          {node.topics.map((topic) => (
            <span className="topic-chip" key={topic}>
              {topic}
            </span>
          ))}
        </div>
      ) : null}
      {node.kind === "image" || node.kind === "video" ? (
        <div className="detail-block">
          <div className="drawer-label">media</div>
          <div className="detail-media-shell">
            <div className="detail-media-head">
              <span className={`status-pill ${mediaStatusTone(effectiveMediaStatus)}`}>
                {mediaStatusLabel(effectiveMediaStatus)}
              </span>
              <div className="detail-media-meta">
                {mediaAsset?.filename ? <span>{mediaAsset.filename}</span> : null}
                {mediaAsset?.size_bytes ? <span>{formatBytes(mediaAsset.size_bytes)}</span> : null}
                {durationSeconds ? <span>{Math.round(durationSeconds)}s</span> : null}
              </div>
            </div>
            {node.kind === "image" && imageSource ? (
              <img className="detail-media" src={imageSource} alt={node.title ?? "image node"} loading="lazy" />
            ) : null}
            {node.kind === "video" && videoSource ? (
              <video
                className="detail-video"
                controls
                preload="metadata"
                poster={imageSource ?? undefined}
                src={videoSource}
              />
            ) : null}
            {node.kind === "video" && !videoSource && imageSource ? (
              <img className="detail-media" src={imageSource} alt={node.title ?? "video preview"} loading="lazy" />
            ) : null}
            {!imageSource && !videoSource ? (
              <div className="drawer-empty">
                {effectiveMediaStatus === "failed"
                  ? "Media processing failed."
                  : "Media is still being prepared."}
              </div>
            ) : null}
            {mediaAsset?.error_message ? <div className="drawer-error">{mediaAsset.error_message}</div> : null}
            {mediaError ? <div className="drawer-error">{mediaError}</div> : null}
            {canRetry ? (
              <button className="drawer-action" type="button" onClick={() => void handleRetry()} disabled={mediaBusy}>
                {mediaBusy ? "retrying..." : "retry processing"}
              </button>
            ) : null}
          </div>
        </div>
      ) : null}
      {node.reply_to_node_id ? (
        <div className="detail-block">
          <div className="drawer-label">reply branch</div>
          <button className="detail-link" type="button" onClick={() => onFocus(node.reply_to_node_id ?? "")}>
            jump to parent
          </button>
        </div>
      ) : null}
      {node.quote_of_node_id ? (
        <div className="detail-block">
          <div className="drawer-label">quoted node</div>
          <button className="detail-link" type="button" onClick={() => onFocus(node.quote_of_node_id ?? "")}>
            jump to quoted source
          </button>
        </div>
      ) : null}
      {thread?.quoted_node ? (
        <div className="detail-block">
          <div className="drawer-label">quoted context</div>
          <button className="thread-context-card" type="button" onClick={() => onFocus(thread.quoted_node?.id ?? "")}>
            <strong>{nodeDisplayLabel(thread.quoted_node, 72)}</strong>
            <span>{thread.quoted_node.preview_text ?? thread.quoted_node.content_text}</span>
          </button>
        </div>
      ) : null}
      <div className="detail-block">
        <div className="drawer-label">thread</div>
        <div className="thread-shell">
          <div className="thread-root">
            <strong>{thread?.root.author_display_name ?? node.author_display_name ?? "You"}</strong>
            <p>{thread?.root.content_text ?? node.content_text ?? "No body text."}</p>
          </div>
          <div className="thread-list">
            {thread?.replies?.length ? (
              thread.replies.map((reply) => (
                <article key={reply.id} className="thread-reply">
                  <div className="thread-reply-head">
                    <button className="thread-reply-author" type="button" onClick={() => reply.author_id && onOpenProfile(reply.author_id)}>
                      {reply.author_display_name ?? "Unknown"}
                    </button>
                    <small>{relativeTime(reply.created_at)}</small>
                  </div>
                  <p>{reply.preview_text ?? reply.content_text}</p>
                  <div className="thread-reply-meta">
                    {reply.reply_to_node_id ? <button type="button" onClick={() => onFocus(reply.reply_to_node_id ?? "")}>parent</button> : null}
                    {reply.quote_of_node_id ? <button type="button" onClick={() => onFocus(reply.quote_of_node_id ?? "")}>quote</button> : null}
                  </div>
                </article>
              ))
            ) : (
              <div className="drawer-empty">No replies yet.</div>
            )}
          </div>
        </div>
      </div>
      <div className="detail-block">
        <div className="drawer-label">connections</div>
        <div className="chip-row">
          {neighbors.length > 0 ? (
            neighbors.map((item) => <NodeChip key={item.id} node={item} onFocus={onFocus} />)
          ) : (
            <span className="drawer-empty">No linked nodes.</span>
          )}
        </div>
      </div>
      <div className="detail-block">
        <div className="drawer-label">related ideas</div>
        {relatedLoading ? <div className="drawer-empty">mapping related ideas...</div> : null}
        {relatedError ? <div className="drawer-error">{relatedError}</div> : null}
        {!relatedLoading && !relatedError && !relatedIdeas?.items.length ? (
          <div className="drawer-empty">No related ideas yet.</div>
        ) : null}
        {relatedIdeas?.explanation_summary ? (
          <div className="drawer-copy">{relatedIdeas.explanation_summary}</div>
        ) : null}
        <div className="detail-related-list">
          {relatedIdeas?.items.slice(0, 4).map((item) => (
            <button
              key={item.node.id}
              type="button"
              className="detail-related-card"
              onClick={() => onFocus(item.node.id)}
            >
              <div className="detail-related-head">
                <strong>{nodeDisplayLabel(item.node, 72)}</strong>
                <span>{formatDiscoveryScore(item.explanation.score_breakdown.total)}</span>
              </div>
              <small>{discoveryReasonLabel(item.explanation.primary_reason)}</small>
              <p>Why shown: {item.explanation.summary}</p>
            </button>
          ))}
        </div>
      </div>
      {node.link_url ? (
        <a className="detail-link" href={node.link_url} target="_blank" rel="noreferrer">
          open link
        </a>
      ) : null}
      {node.metadata_json && Object.keys(node.metadata_json).length > 0 ? (
        <div className="detail-block">
          <div className="drawer-label">metadata</div>
          <pre className="metadata-pre">{JSON.stringify(node.metadata_json, null, 2)}</pre>
        </div>
      ) : null}
    </aside>
  );
}

function OnboardingPrompt({
  me,
  onComplete,
}: {
  me: MeRead | null;
  onComplete: () => Promise<void>;
}) {
  if (!me || me.onboarding_v2_completed) return null;

  return (
    <div className="onboarding-card">
      <div className="drawer-label">onboarding</div>
      <h3>Finish your graph profile</h3>
      <p>Set your display name, bio, and public visibility before expanding the graph.</p>
      <button className="drawer-action" onClick={() => void onComplete()} type="button">
        mark complete
      </button>
    </div>
  );
}

function SystemsOverlay({
  open,
  onClose,
  onFocusNode,
}: {
  open: boolean;
  onClose: () => void;
  onFocusNode: (nodeId: string) => void;
}) {
  if (!open) return null;

  return (
    <>
      <div className="drawer-backdrop visible" onClick={onClose} />
      <aside className="systems-overlay" onClick={(event) => event.stopPropagation()}>
        <div className="drawer-header systems-overlay-head">
          <div>
            <div className="drawer-label">cto command center</div>
            <div className="drawer-title">Phases 6-12 prototype surface</div>
          </div>
          <button className="drawer-close" onClick={onClose} type="button">
            x
          </button>
        </div>
        <LaterPhaseCommandCenter
          onFocusNode={(nodeId) => {
            onClose();
            onFocusNode(nodeId);
          }}
        />
      </aside>
    </>
  );
}

export function GraphShell() {
  const [session, setSession] = useState<SessionPayload | null>(() => loadSession());
  const [graph, setGraph] = useState<GraphNativeResponse | null>(null);
  const [me, setMe] = useState<MeRead | null>(null);
  const [loadingGraph, setLoadingGraph] = useState(false);
  const [graphError, setGraphError] = useState<string | null>(null);
  const [socialError, setSocialError] = useState<string | null>(null);
  const [socialMode, setSocialMode] = useState(false);
  const [viewport, setViewport] = useState<GraphViewport>(DEFAULT_VIEWPORT);
  const [homeViewport, setHomeViewport] = useState<GraphViewport>(DEFAULT_VIEWPORT);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [focusedNodeId, setFocusedNodeId] = useState<string | null>(null);
  const [detailNode, setDetailNode] = useState<NodeRead | null>(null);
  const [detailThread, setDetailThread] = useState<NodeThreadResponse | null>(null);
  const [detailCluster, setDetailCluster] = useState<GraphClusterRecord | null>(null);
  const [composerOpen, setComposerOpen] = useState(false);
  const [composerBusy, setComposerBusy] = useState(false);
  const [composerContext, setComposerContext] = useState<NodeRead | null>(null);
  const [composerDraft, setComposerDraft] = useState<Partial<NodeCreateRequest> | null>(null);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<GraphSearchResult[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [discoveryOpen, setDiscoveryOpen] = useState(false);
  const [discoveryQuery, setDiscoveryQuery] = useState("");
  const [discoveryFilters, setDiscoveryFilters] = useState<DiscoveryExploreFilters>({
    high_evidence: true,
    limit: 8,
  });
  const [discoveryResults, setDiscoveryResults] = useState<DiscoveryExploreResponse | null>(null);
  const [discoveryLoading, setDiscoveryLoading] = useState(false);
  const [discoveryError, setDiscoveryError] = useState<string | null>(null);
  const [adjacentPeople, setAdjacentPeople] = useState<AdjacentPeopleResponse | null>(null);
  const [adjacentLoading, setAdjacentLoading] = useState(false);
  const [systemsOpen, setSystemsOpen] = useState(false);
  const [socialDrawerOpen, setSocialDrawerOpen] = useState(false);
  const [peopleQuery, setPeopleQuery] = useState("");
  const [peopleResults, setPeopleResults] = useState<SocialSearchResult[]>([]);
  const [peopleLoading, setPeopleLoading] = useState(false);
  const [activeProfileUserId, setActiveProfileUserId] = useState<string | null>(null);
  const [activeProfile, setActiveProfile] = useState<SocialProfileRead | null>(null);
  const [activeProfileLoading, setActiveProfileLoading] = useState(false);
  const [friends, setFriends] = useState<FriendsResponse | null>(null);
  const [neighborhood, setNeighborhood] = useState<SocialNeighborhoodResponse | null>(null);
  const [socialBusy, setSocialBusy] = useState(false);
  const [authOpen, setAuthOpen] = useState(!session);
  const [authNotice, setAuthNotice] = useState<string | null>(null);
  const trailRef = useRef<string[]>([]);
  const deferredGraphSearch = useDeferredValue(searchQuery);
  const deferredDiscoveryQuery = useDeferredValue(discoveryQuery);
  const deferredPeopleSearch = useDeferredValue(peopleQuery);

  const trail = useMemo(() => {
    if (!graph) return [];
    const seen = new Set<string>();
    return trailRef.current
      .map((id) => graph.nodes.find((node) => node.id === id))
      .filter((node): node is GraphNodeRecord => Boolean(node))
      .filter((node) => {
        if (seen.has(node.id)) return false;
        seen.add(node.id);
        return true;
      });
  }, [graph]);

  const loadGraph = useMemo(
    () => async (nextSocialMode = socialMode) => {
      if (!session) {
        setGraph(null);
        return;
      }
      setLoadingGraph(true);
      setGraphError(null);
      try {
        const nextGraph = await graphApi.getGraph(nextSocialMode);
        setGraph(nextGraph);
        setSocialMode(nextGraph.social_mode);
        setViewport(nextGraph.viewport);
        setHomeViewport(nextGraph.viewport);
      } catch (err) {
        setGraphError(err instanceof Error ? err.message : "Could not load graph.");
      } finally {
        setLoadingGraph(false);
      }
    },
    [session, socialMode],
  );

  const loadMe = useMemo(
    () => async () => {
      if (!session) {
        setMe(null);
        return;
      }
      try {
        setMe(await graphApi.getMe());
      } catch (err) {
        setGraphError(err instanceof Error ? err.message : "Could not load profile.");
      }
    },
    [session],
  );

  const loadSocialLists = useMemo(
    () => async () => {
      if (!session) return;
      try {
        const [nextFriends, nextNeighborhood] = await Promise.all([
          graphApi.getFriends(),
          graphApi.getNeighborhood(),
        ]);
        setFriends(nextFriends);
        setNeighborhood(nextNeighborhood);
      } catch (err) {
        setSocialError(err instanceof Error ? err.message : "Could not load social context.");
      }
    },
    [session],
  );

  const refreshWorkspace = useMemo(
    () => async () => {
      await Promise.all([loadGraph(socialMode), loadMe(), loadSocialLists()]);
    },
    [loadGraph, loadMe, loadSocialLists, socialMode],
  );

  useEffect(() => {
    if (!session) {
      setAuthOpen(true);
      setGraph(null);
      setMe(null);
      return;
    }
    setAuthOpen(false);
    void refreshWorkspace();
  }, [session]);

  useEffect(() => {
    const handleSessionExpired = () => {
      setSession(null);
      setGraph(null);
      setMe(null);
      setGraphError("Your session expired. Please sign in again.");
      setAuthNotice("Your session expired. Please sign in again.");
      setAuthOpen(true);
    };

    window.addEventListener("thoughtgraph:session-expired", handleSessionExpired);
    return () => window.removeEventListener("thoughtgraph:session-expired", handleSessionExpired);
  }, []);

  useEffect(() => {
    if (!searchOpen || deferredGraphSearch.trim().length < 2) {
      setSearchResults([]);
      return;
    }

    let cancelled = false;
    setSearchLoading(true);
    void graphApi
      .searchGraph(deferredGraphSearch.trim())
      .then((response) => {
        if (!cancelled) setSearchResults(response.items);
      })
      .catch(() => {
        if (!cancelled) setSearchResults([]);
      })
      .finally(() => {
        if (!cancelled) setSearchLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [deferredGraphSearch, searchOpen]);

  useEffect(() => {
    if (!session || !discoveryOpen) {
      return;
    }

    let cancelled = false;
    setDiscoveryLoading(true);
    setDiscoveryError(null);
    void graphApi
      .getDiscoveryExplore({
        ...discoveryFilters,
        q: deferredDiscoveryQuery.trim() || undefined,
      })
      .then((response) => {
        if (!cancelled) {
          setDiscoveryResults(response);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setDiscoveryResults(null);
          setDiscoveryError(err instanceof Error ? err.message : "Could not load discovery.");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setDiscoveryLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [deferredDiscoveryQuery, discoveryFilters, discoveryOpen, graph?.explanation.generated_at, session]);

  useEffect(() => {
    if (!session || !discoveryOpen) {
      return;
    }

    let cancelled = false;
    setAdjacentLoading(true);
    void graphApi
      .getAdjacentPeople(6)
      .then((response) => {
        if (!cancelled) {
          setAdjacentPeople(response);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setDiscoveryError(err instanceof Error ? err.message : "Could not load adjacent people.");
          setAdjacentPeople(null);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setAdjacentLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [discoveryOpen, graph?.explanation.generated_at, session]);

  useEffect(() => {
    if (!socialDrawerOpen || deferredPeopleSearch.trim().length < 2) {
      setPeopleResults([]);
      return;
    }

    let cancelled = false;
    setPeopleLoading(true);
    setSocialError(null);
    void graphApi
      .searchUsers(deferredPeopleSearch.trim())
      .then((response) => {
        if (!cancelled) setPeopleResults(response);
      })
      .catch(() => {
        if (!cancelled) setPeopleResults([]);
      })
      .finally(() => {
        if (!cancelled) setPeopleLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [deferredPeopleSearch, socialDrawerOpen]);

  useEffect(() => {
    const detailNodeId = focusedNodeId ?? selectedNodeId;
    if (!session || !detailNodeId) {
      setDetailNode(null);
      setDetailThread(null);
      setDetailCluster(null);
      return;
    }

    const base = graph?.nodes.find((node) => node.id === detailNodeId) ?? null;
    setDetailNode((current) =>
      base ? fallbackNodeRead(base) : current?.id === detailNodeId ? current : null,
    );
    setDetailThread(null);
    setDetailCluster(graph?.clusters.find((cluster) => cluster.id === base?.cluster_id) ?? null);

    let cancelled = false;
    void graphApi
      .getNodeThread(detailNodeId)
      .then((response) => {
        if (cancelled) return;
        setDetailThread(response);
        setDetailNode(response.root);
        if (response.root) {
          trailRef.current = [response.root.id, ...trailRef.current.filter((id) => id !== response.root.id)].slice(0, 6);
        }
      })
      .catch(() => {
        if (cancelled) return;
        setDetailThread(null);
        if (base) {
          setDetailNode(fallbackNodeRead(base));
          void graphApi
            .getNode(detailNodeId)
            .then((node) => {
              if (!cancelled) setDetailNode(node);
            })
            .catch(() => {
              if (!cancelled) setDetailNode(fallbackNodeRead(base));
            });
        } else {
          setDetailNode(null);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [focusedNodeId, graph, selectedNodeId, session]);

  useEffect(() => {
    if (!socialDrawerOpen || !activeProfileUserId) {
      setActiveProfile(null);
      return;
    }

    let cancelled = false;
    setActiveProfileLoading(true);
    setSocialError(null);
    void graphApi
      .getUserProfile(activeProfileUserId)
      .then((profile) => {
        if (!cancelled) setActiveProfile(profile);
      })
      .catch((err) => {
        if (!cancelled) {
          setSocialError(err instanceof Error ? err.message : "Could not load profile.");
          setActiveProfile(null);
        }
      })
      .finally(() => {
        if (!cancelled) setActiveProfileLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [activeProfileUserId, socialDrawerOpen]);

  useEffect(() => {
    const handleShortcut = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setSearchOpen(true);
      }
      if (event.key === "/") {
        const target = event.target as HTMLElement | null;
        if (!target || (target.tagName !== "INPUT" && target.tagName !== "TEXTAREA")) {
          event.preventDefault();
          setSearchOpen(true);
        }
      }
      if (event.key === "Escape") {
        setSearchOpen(false);
        setDiscoveryOpen(false);
        setSystemsOpen(false);
        if (!composerBusy) {
          setComposerOpen(false);
          setSelectedNodeId(null);
          setFocusedNodeId(null);
          setDetailNode(null);
          setDetailThread(null);
        }
        setSocialDrawerOpen(false);
      }
    };

    window.addEventListener("keydown", handleShortcut);
    return () => window.removeEventListener("keydown", handleShortcut);
  }, [composerBusy]);

  const focusNode = (nodeId: string) => {
    if (!graph) return;
    const node = graph.nodes.find((item) => item.id === nodeId);
    if (!node) return;
    setSelectedNodeId(node.id);
    setFocusedNodeId(node.id);
    setViewport(focusViewportFor(node, viewport));
  };

  const jumpToNode = (nodeId: string) => {
    focusNode(nodeId);
    setSearchOpen(false);
  };

  const openDiscoveredNode = (node: GraphNodeRecord) => {
    const graphNode = graph?.nodes.find((item) => item.id === node.id);
    if (graphNode) {
      focusNode(graphNode.id);
      return;
    }
    setSelectedNodeId(node.id);
    setFocusedNodeId(node.id);
    setDetailNode(fallbackNodeRead(node));
    setDetailThread(null);
    setDetailCluster(null);
  };

  const openProfile = (userId?: string | null) => {
    if (!userId) return;
    setSocialDrawerOpen(true);
    setActiveProfileUserId(userId);
  };

  const returnToSelf = () => {
    setSelectedNodeId(null);
    setFocusedNodeId(null);
    setDetailNode(null);
    setDetailThread(null);
    setViewport(homeViewport);
  };

  const updateMe = async (payload: MeUpdateRequest) => {
    const next = await graphApi.updateMe(payload);
    setMe(next);
    return next;
  };

  const createNode = async (payload: NodeCreateRequest) => {
    await graphApi.createNode(payload);
    await refreshWorkspace();
  };

  const refreshSocialContext = async () => {
    await loadSocialLists();
    if (activeProfileUserId) {
      try {
        setActiveProfile(await graphApi.getUserProfile(activeProfileUserId));
      } catch {
        // ignored; drawer already has enough state to stay open
      }
    }
  };

  const handleLogout = async () => {
    try {
      await graphApi.logout();
    } finally {
      clearSession();
      setSession(null);
      setGraph(null);
      setMe(null);
      setDiscoveryResults(null);
      setAdjacentPeople(null);
      setSelectedNodeId(null);
      setFocusedNodeId(null);
      setDetailNode(null);
      setDetailThread(null);
      setAuthOpen(true);
      setAuthNotice(null);
    }
  };

  const handleAuthenticated = (nextSession: SessionPayload) => {
    saveSession(nextSession);
    setAuthNotice(null);
    setSession(nextSession);
    setAuthOpen(false);
  };

  const toggleSocialMode = () => {
    const nextSocialMode = !socialMode;
    setSocialMode(nextSocialMode);
    setSelectedNodeId(null);
    setFocusedNodeId(null);
    setDetailNode(null);
    setDetailThread(null);
    void loadGraph(nextSocialMode);
  };

  const toggleDiscoveryFilter = (key: keyof DiscoveryExploreFilters) => {
    setDiscoveryFilters((current) => ({
      ...current,
      [key]: !current[key],
    }));
  };

  const selectedContext = detailNode;

  const openComposer = (
    mode: "new" | "reply" | "quote",
    draft?: Partial<NodeCreateRequest> | null,
  ) => {
    const target = mode === "new" ? null : selectedContext;
    setComposerContext(target);
    setComposerDraft({
      ...(draft ?? {}),
      ...(mode === "reply" && target ? { reply_to_node_id: target.id, quote_of_node_id: null } : {}),
      ...(mode === "quote" && target ? { reply_to_node_id: null, quote_of_node_id: target.id } : {}),
    });
    setComposerOpen(true);
  };

  const handleRelationshipAction = async (
    userId: string,
    action:
      | { kind: "follow"; following: boolean }
      | { kind: "friend"; action: "request" | "accept" | "decline" | "remove" }
      | { kind: "restriction"; restriction: RestrictionUpdate["kind"]; active: boolean },
  ) => {
    setSocialBusy(true);
    setSocialError(null);
    try {
      if (action.kind === "follow") {
        if (action.following) {
          await graphApi.unfollowUser(userId);
        } else {
          await graphApi.followUser(userId);
        }
      } else if (action.kind === "friend") {
        if (action.action === "request") await graphApi.requestFriend(userId);
        if (action.action === "accept") await graphApi.acceptFriend(userId);
        if (action.action === "decline") await graphApi.declineFriend(userId);
        if (action.action === "remove") await graphApi.removeFriend(userId);
      } else {
        await graphApi.updateRestriction(userId, { kind: action.restriction, active: action.active });
      }
      await refreshSocialContext();
    } catch (err) {
      setSocialError(err instanceof Error ? err.message : "Could not update relationship.");
    } finally {
      setSocialBusy(false);
    }
  };

  const markOnboardingComplete = async () => {
    if (!me) return;
    await updateMe({ onboarding_v2_completed: true });
  };

  const firstGraphVisible = Boolean(me && graph && me.node_count === 0 && graph.nodes.length === 0);

  if (!session || authOpen) {
    return <AuthLanding onAuthenticated={handleAuthenticated} notice={authNotice} />;
  }

  return (
    <div className="graph-shell">
      <div className="graph-shell-bg" />
      <GraphHeader
        session={session}
        me={me}
        graph={graph}
        socialMode={socialMode}
        syncing={loadingGraph}
        onOpenDiscovery={() => setDiscoveryOpen(true)}
        onOpenSystems={() => setSystemsOpen(true)}
        onToggleSocialMode={toggleSocialMode}
        onOpenComposer={() => openComposer("new")}
        onOpenProfile={() => openProfile(me?.id)}
        onOpenPeople={() => {
          setSocialDrawerOpen(true);
          setActiveProfileUserId(activeProfileUserId ?? me?.id ?? null);
          void refreshSocialContext();
        }}
        onOpenSearch={() => setSearchOpen(true)}
        onLogout={() => void handleLogout()}
        onReturnToSelf={returnToSelf}
        onJumpToNode={jumpToNode}
        trail={trail}
      />
      <main className="graph-stage">
        <GraphCanvas
          graph={graph}
          viewport={viewport}
          selectedNodeId={selectedNodeId}
          focusedNodeId={focusedNodeId}
          onViewportChange={setViewport}
          onNodeSelect={(nodeId) => setSelectedNodeId(nodeId)}
          onNodeFocus={setFocusedNodeId}
        />
        <MiniMap graph={graph} viewport={viewport} onJump={setViewport} />
        <OnboardingPrompt me={me} onComplete={markOnboardingComplete} />
        <EmptyGraphPrompt
          visible={firstGraphVisible}
          onStart={(starter) =>
            openComposer(
              "new",
              starter
                ? {
                    kind: "thought",
                    title: starter.title,
                    content_text: starter.content_text,
                    visibility: starter.visibility,
                  }
                : {
                    kind: "thought",
                    visibility: "private",
                  },
            )
          }
        />
      </main>
      {detailNode ? (
        <NodeDetailPanel
          node={detailNode}
          thread={detailThread}
          cluster={detailCluster}
          graph={graph}
          onRefreshWorkspace={refreshWorkspace}
          onFocus={jumpToNode}
          onOpenProfile={openProfile}
          onComposeReply={() => openComposer("reply")}
          onComposeQuote={() => openComposer("quote")}
          onClose={returnToSelf}
        />
      ) : null}
      <SearchPanel
        open={searchOpen}
        query={searchQuery}
        results={searchResults}
        loading={searchLoading}
        onClose={() => setSearchOpen(false)}
        onQueryChange={setSearchQuery}
        onFocus={jumpToNode}
      />
      <DiscoveryDrawer
        open={discoveryOpen}
        query={discoveryQuery}
        filters={discoveryFilters}
        availability={discoveryResults?.filter_availability ?? null}
        explore={discoveryResults}
        adjacent={adjacentPeople}
        loading={discoveryLoading}
        peopleLoading={adjacentLoading}
        error={discoveryError}
        onClose={() => setDiscoveryOpen(false)}
        onQueryChange={setDiscoveryQuery}
        onToggleFilter={toggleDiscoveryFilter}
        onOpenNode={openDiscoveredNode}
        onOpenProfile={(userId) => {
          setDiscoveryOpen(false);
          openProfile(userId);
        }}
      />
      <SystemsOverlay open={systemsOpen} onClose={() => setSystemsOpen(false)} onFocusNode={jumpToNode} />
      <SocialDrawer
        open={socialDrawerOpen}
        me={me}
        query={peopleQuery}
        queryResults={peopleResults}
        queryLoading={peopleLoading}
        activeProfile={activeProfile}
        activeProfileLoading={activeProfileLoading}
        friends={friends}
        neighborhood={neighborhood}
        onClose={() => setSocialDrawerOpen(false)}
        onQueryChange={setPeopleQuery}
        onSelectUser={(userId) => {
          setSocialDrawerOpen(true);
          setActiveProfileUserId(userId);
        }}
        onRefreshProfile={(userId) => {
          setActiveProfileUserId(userId);
          void refreshSocialContext();
        }}
        onToggleFollow={(userId, following) => handleRelationshipAction(userId, { kind: "follow", following })}
        onRequestFriend={(userId) => handleRelationshipAction(userId, { kind: "friend", action: "request" })}
        onAcceptFriend={(userId) => handleRelationshipAction(userId, { kind: "friend", action: "accept" })}
        onDeclineFriend={(userId) => handleRelationshipAction(userId, { kind: "friend", action: "decline" })}
        onRemoveFriend={(userId) => handleRelationshipAction(userId, { kind: "friend", action: "remove" })}
        onToggleRestriction={(userId, kind, active) =>
          handleRelationshipAction(userId, { kind: "restriction", restriction: kind, active })
        }
        busy={socialBusy}
        error={socialError}
      />
      <NodeComposer
        open={composerOpen}
        contextNode={composerContext}
        draft={composerDraft}
        onClose={() => setComposerOpen(false)}
        onCreate={createNode}
        onBusyChange={setComposerBusy}
      />
      {graphError ? <div className="global-error">{graphError}</div> : null}
      {loadingGraph ? <div className="global-status">loading graph</div> : null}
    </div>
  );
}
