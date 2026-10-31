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

  it("explains truncated JSON instead of a SyntaxError", () => {
    expect(() => readApiPayload('{"id":"cut-off', "application/json", 200)).toThrow(/incomplete response/i);
  });

  it("reads FastAPI validation detail arrays", () => {
    expect(() =>
      readApiPayload(
        JSON.stringify({ detail: [{ loc: ["body", "email"], msg: "value is not a valid email address" }] }),
        "application/json",
        422,
      ),
    ).toThrow(/valid email address/i);
  });

  it("explains Starlette Invalid host header instead of incomplete JSON", () => {
    expect(() => readApiPayload("Invalid host header", "text/plain", 400)).toThrow(/TRUSTED_HOSTS/i);
  });

  it("surfaces a sanitized preview for other plain-text errors", () => {
    expect(() => readApiPayload("upstream exploded", "text/plain", 500)).toThrow(/upstream exploded/);
  });
});
