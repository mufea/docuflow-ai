import { looksHtml, messageForNonJsonBody } from "./api-proxy";

export function readApiPayload(text: string, contentType: string, status: number): Record<string, unknown> {
  const trimmed = text.trim();
  if (looksHtml(trimmed, contentType) || (trimmed && !contentType.includes("json") && trimmed.startsWith("<"))) {
    throw new Error(messageForNonJsonBody(text, status, contentType));
  }
  let data: Record<string, unknown> = {};
  if (trimmed) {
    try {
      data = JSON.parse(text) as Record<string, unknown>;
    } catch {
      throw new Error(messageForNonJsonBody(text, status, contentType));
    }
  }
  if (status < 200 || status >= 300) {
    throw new Error(errorMessage(data, status));
  }
  return data;
}

function errorMessage(data: Record<string, unknown>, status: number): string {
  if (typeof data.message === "string") return data.message;
  if (typeof data.detail === "string") return data.detail;
  if (Array.isArray(data.detail) && data.detail[0] && typeof data.detail[0] === "object") {
    const first = data.detail[0] as Record<string, unknown>;
    if (typeof first.msg === "string") return first.msg;
  }
  return `Request failed (${status})`;
}
