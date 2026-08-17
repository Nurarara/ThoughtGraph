import { describe, expect, it } from "vitest";

import { canReuseUploadedAsset, resolveComposerVisibility } from "./composerDecisions";

describe("resolveComposerVisibility", () => {
  it("honors an explicit draft visibility", () => {
    expect(resolveComposerVisibility("public", "private")).toBe("public");
  });

  it("inherits valid context visibility without broadening private content", () => {
    expect(resolveComposerVisibility(undefined, "private")).toBe("private");
    expect(resolveComposerVisibility(undefined, "friends")).toBe("friends");
  });

  it("falls back to private for missing or unknown context", () => {
    expect(resolveComposerVisibility(undefined, null)).toBe("private");
    expect(resolveComposerVisibility(undefined, "unknown")).toBe("private");
  });
});

describe("canReuseUploadedAsset", () => {
  it.each(["uploaded", "processing", "ready"])("reuses a matching %s asset", (status) => {
    expect(canReuseUploadedAsset({ kind: "image", status }, "image")).toBe(true);
  });

  it("rejects incomplete, failed, and wrong-kind assets", () => {
    expect(canReuseUploadedAsset(null, "image")).toBe(false);
    expect(canReuseUploadedAsset({ kind: "image", status: "awaiting_upload" }, "image")).toBe(false);
    expect(canReuseUploadedAsset({ kind: "image", status: "failed" }, "image")).toBe(false);
    expect(canReuseUploadedAsset({ kind: "video", status: "ready" }, "image")).toBe(false);
  });
});
