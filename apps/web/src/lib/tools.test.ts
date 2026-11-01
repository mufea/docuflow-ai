import { describe, expect, it } from "vitest";
import { toolBySlug, TOOLS } from "./tools";

describe("tool catalog", () => {
  it("includes the core PDF operations", () => {
    const slugs = TOOLS.map((tool) => tool.slug);
    expect(slugs).toContain("merge");
    expect(slugs).toContain("unlock");
    expect(toolBySlug("compress")?.name).toBe("Compress PDF");
    expect(toolBySlug("docx_to_pdf")?.description).toMatch(/Word document to PDF/i);
  });

  it("does not point ask at a fake placeholder", () => {
    expect(toolBySlug("ask")?.href).toBe("/app/assistant");
  });
});
