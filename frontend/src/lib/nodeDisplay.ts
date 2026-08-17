export interface NodeDisplaySource {
  title?: string | null;
  preview_text?: string | null;
  content_text?: string | null;
}

export function nodeDisplayLabel(node: NodeDisplaySource, maxLength = 64): string {
  const value = [node.title, node.preview_text, node.content_text]
    .map((candidate) => candidate?.replace(/\s+/g, " ").trim() ?? "")
    .find(Boolean) || "Untitled node";
  if (value.length <= maxLength) return value;
  return `${value.slice(0, Math.max(1, maxLength - 1)).trimEnd()}…`;
}
