import { describe, expect, it } from "vitest";
import { readApiPayload } from "./api-payload";

describe("readApiPayload", () => {
  it("parses JSON success bodies", () => {
    expect(readApiPayload('{"id":"u1"}', "application/json", 200)).toEqual({ id: "u1" });
  });

  it("explains HTML from a sleeping or misrouted API", () => {
    expect(() =>
      readApiPayload("<!DOCTYPE html><html><body>Starting</body></html>", "text/html", 200),
    ).toThrow(/web page instead of JSON/i);
  });

  it("explains a 503 HTML wake-up page", () => {
    expect(() => readApiPayload("<!DOCTYPE html>", "text/html", 503)).toThrow(/API is starting/i);
  });
});
