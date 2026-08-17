export type ComposerVisibility = "private" | "friends" | "public";

export function resolveComposerVisibility(
  draftVisibility: ComposerVisibility | undefined,
  contextVisibility: string | null | undefined,
): ComposerVisibility {
  if (draftVisibility) return draftVisibility;
  if (contextVisibility === "private" || contextVisibility === "friends" || contextVisibility === "public") {
    return contextVisibility;
  }
  return "private";
}

export function canReuseUploadedAsset(
  asset: { kind: string; status: string } | null,
  kind: "image" | "video",
): boolean {
  return Boolean(asset && asset.kind === kind && ["uploaded", "processing", "ready"].includes(asset.status));
}
