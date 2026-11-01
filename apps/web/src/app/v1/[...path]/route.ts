import { type NextRequest } from "next/server";

import {
  API_UNREACHABLE_MESSAGE,
  apiOriginFromEnv,
  isBinaryContentType,
  isLocalPlaceholder,
  isSelfProxy,
  isValidJson,
  looksHtml,
  looksInvalidHost,
  looksJsonObjectOrArray,
  messageForNonJsonBody,
  MISSING_API_URL_MESSAGE,
  PRIVATE_NETWORK_MESSAGE,
  SELF_PROXY_MESSAGE,
  shouldRetryUpstream,
} from "@/lib/api-proxy";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

function jsonError(status: number, message: string) {
  return Response.json({ message }, { status });
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function decodeText(payload: ArrayBuffer): string {
  return new TextDecoder("utf-8").decode(payload);
}

function shouldRewriteAsJson(text: string, contentType: string): boolean {
  if (isBinaryContentType(contentType)) return false;
  const trimmed = text.trim();
  if (!trimmed) return false;
  if (isValidJson(trimmed)) return false;
  return (
    looksInvalidHost(trimmed) ||
    looksHtml(trimmed, contentType) ||
    looksJsonObjectOrArray(trimmed) ||
    contentType.includes("json") ||
    contentType.includes("text/") ||
    !contentType
  );
}

async function fetchApi(
  target: string,
  init: RequestInit,
  attempts = 4,
): Promise<{ response: Response; payload: ArrayBuffer }> {
  let lastError: unknown;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    if (attempt > 0) {
      await sleep(3000 * attempt);
    }
    try {
      const response = await fetch(target, init);
      const payload = await response.arrayBuffer();
      const contentType = response.headers.get("content-type") || "";
      if (isBinaryContentType(contentType)) {
        return { response, payload };
      }
      const text = decodeText(payload);
      if (shouldRetryUpstream(response.status, text, contentType)) {
        lastError = new Error("html-or-unavailable");
        continue;
      }
      return { response, payload };
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError instanceof Error ? lastError : new Error("API unreachable");
}

async function proxy(request: NextRequest, path: string[]) {
  const origin = apiOriginFromEnv({
    API_INTERNAL_URL: process.env.API_INTERNAL_URL,
    DOCUFLOW_PUBLIC_API_URL: process.env.DOCUFLOW_PUBLIC_API_URL,
  });
  const incomingHost = request.headers.get("host") || request.nextUrl.host;
  if (process.env.NODE_ENV === "production" && isLocalPlaceholder(origin)) {
    return jsonError(503, MISSING_API_URL_MESSAGE);
  }
  if (
    process.env.NODE_ENV === "production" &&
    origin.startsWith("http://") &&
    !origin.includes("onrender.com")
  ) {
    return jsonError(503, PRIVATE_NETWORK_MESSAGE);
  }
  if (origin && isSelfProxy(origin, incomingHost)) {
    return jsonError(503, SELF_PROXY_MESSAGE);
  }

  const base = origin || "http://127.0.0.1:43124";
  const target = `${base}/v1/${path.join("/")}${request.nextUrl.search}`;
  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  const cookie = request.headers.get("cookie");
  const csrf = request.headers.get("x-csrf-token");
  const originHeader = request.headers.get("origin");
  headers.set("accept", "application/json");
  headers.set("accept-encoding", "identity");
  if (contentType) headers.set("content-type", contentType);
  if (cookie) headers.set("cookie", cookie);
  if (csrf) headers.set("x-csrf-token", csrf);
  if (originHeader) headers.set("origin", originHeader);
  if (incomingHost) headers.set("x-docuflow-web-host", incomingHost);

  const method = request.method;
  const hasBody = !["GET", "HEAD"].includes(method);
  const body = hasBody ? await request.arrayBuffer() : undefined;

  let response: Response;
  let payload: ArrayBuffer;
  try {
    ({ response, payload } = await fetchApi(target, {
      method,
      headers,
      body,
      redirect: "manual",
      cache: "no-store",
    }));
  } catch {
    return jsonError(503, API_UNREACHABLE_MESSAGE);
  }

  const upstreamType = response.headers.get("content-type") || "";
  if (!isBinaryContentType(upstreamType)) {
    const text = decodeText(payload);
    if (shouldRewriteAsJson(text, upstreamType)) {
      const status = response.status >= 400 ? response.status : 502;
      return jsonError(status, messageForNonJsonBody(text, response.status, upstreamType));
    }
  }

  const outbound = new Headers();
  const skip = new Set([
    "content-encoding",
    "transfer-encoding",
    "content-length",
    "connection",
    "keep-alive",
    "set-cookie",
  ]);
  response.headers.forEach((value, key) => {
    if (skip.has(key.toLowerCase())) return;
    outbound.set(key, value);
  });
  outbound.set("content-length", String(payload.byteLength));
  const nextResponse = new Response(payload, { status: response.status, headers: outbound });
  const cookies = response.headers.getSetCookie?.() ?? [];
  for (const cookieValue of cookies) {
    nextResponse.headers.append("set-cookie", cookieValue);
  }
  return nextResponse;
}

export async function GET(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  return proxy(request, path);
}

export async function POST(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  return proxy(request, path);
}

export async function PATCH(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  return proxy(request, path);
}

export async function DELETE(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  return proxy(request, path);
}
