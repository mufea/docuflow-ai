import { describe, expect, it } from "vitest";
import {
  apiOriginFromEnv,
  INVALID_HOST_MESSAGE,
  isLocalPlaceholder,
  isSelfProxy,
  messageForNonJsonBody,
  SELF_PROXY_MESSAGE,
  shouldRetryUpstream,
} from "./api-proxy";

describe("api proxy helpers", () => {
  it("prefers API_INTERNAL_URL and strips a trailing slash", () => {
    expect(
      apiOriginFromEnv({
        API_INTERNAL_URL: "https://docuflow-api.onrender.com/",
        DOCUFLOW_PUBLIC_API_URL: "https://other.example",
      }),
    ).toBe("https://docuflow-api.onrender.com");
  });

  it("treats localhost as a production misconfiguration", () => {
    expect(isLocalPlaceholder("")).toBe(true);
    expect(isLocalPlaceholder("http://127.0.0.1:43124")).toBe(true);
    expect(isLocalPlaceholder("https://docuflow-api.onrender.com")).toBe(false);
  });

  it("detects when the web service is proxying to itself", () => {
    expect(isSelfProxy("https://pdf.example.com", "pdf.example.com")).toBe(true);
    expect(isSelfProxy("https://docuflow-web.onrender.com", "docuflow-web.onrender.com")).toBe(true);
    expect(isSelfProxy("https://docuflow-api.onrender.com", "docuflow-web.onrender.com")).toBe(false);
    expect(SELF_PROXY_MESSAGE).toMatch(/API_INTERNAL_URL points at this web service/i);
  });

  it("retries HTML, wake-up statuses, and truncated JSON but not host rejection", () => {
    expect(shouldRetryUpstream(503, "starting", "text/plain")).toBe(true);
    expect(shouldRetryUpstream(200, "<!DOCTYPE html>", "text/html")).toBe(true);
    expect(shouldRetryUpstream(200, '{"id":"cut-off', "application/json")).toBe(true);
    expect(shouldRetryUpstream(400, "Invalid host header", "text/plain")).toBe(false);
    expect(shouldRetryUpstream(200, '{"id":"ok"}', "application/json")).toBe(false);
  });

  it("maps Invalid host header to a trusted-hosts instruction", () => {
    expect(messageForNonJsonBody("Invalid host header", 400, "text/plain")).toBe(INVALID_HOST_MESSAGE);
  });

  it("keeps a sanitized preview for other plain-text bodies", () => {
    expect(messageForNonJsonBody("Service Unavailable", 502, "text/plain")).toMatch(/Service Unavailable/);
  });
});
