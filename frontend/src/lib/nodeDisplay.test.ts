import { describe, expect, it } from "vitest";

import { nodeDisplayLabel } from "./nodeDisplay";

describe("nodeDisplayLabel", () => {
  it("prefers a normalized title", () => {
    expect(nodeDisplayLabel({ title: "  Durable   graph ", preview_text: "preview" })).toBe("Durable graph");
  });

  it("falls through blank values to preview and content", () => {
    expect(nodeDisplayLabel({ title: "   ", preview_text: "Readable preview", content_text: "body" })).toBe(
      "Readable preview",
    );
    expect(nodeDisplayLabel({ title: null, preview_text: "", content_text: "Full thought" })).toBe("Full thought");
    expect(nodeDisplayLabel({})).toBe("Untitled node");
  });

  it("truncates without exceeding the requested length", () => {
    const label = nodeDisplayLabel({ content_text: "A long thought that needs a compact canvas label" }, 20);
    expect(label).toBe("A long thought that…");
    expect(label).toHaveLength(20);
  });
});
