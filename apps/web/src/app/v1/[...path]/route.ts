import { type NextRequest } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

function apiOrigin(): string {
  const raw = (process.env.API_INTERNAL_URL || process.env.DOCUFLOW_PUBLIC_API_URL || "").trim();
  return raw.replace(/\/$/, "");
}

function isLocalPlaceholder(url: string): boolean {
  return !url || /localhost|127\.0\.0\.1/.test(url);
}

function jsonError(status: number, message: string) {
  return Response.json({ message }, { status });
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function fetchApi(target: string, init: RequestInit, attempts = 4): Promise<Response> {
  let lastError: unknown;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    if (attempt > 0) {
      await sleep(3000 * attempt);
    }
    try {
      const response = await fetch(target, init);
      const contentType = response.headers.get("content-type") || "";
      if (contentType.includes("text/html") || response.status === 502 || response.status === 503) {
        lastError = new Error("html-or-unavailable");
        continue;
      }
      return response;
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError instanceof Error ? lastError : new Error("API unreachable");
}

async function proxy(request: NextRequest, path: string[]) {
  const origin = apiOrigin();
  if (process.env.NODE_ENV === "production" && isLocalPlaceholder(origin)) {
    return jsonError(
      503,
      "The web service is missing API_INTERNAL_URL. Set it to your API’s public https://…onrender.com URL (not localhost).",
    );
  }
  if (
    process.env.NODE_ENV === "production" &&
    origin.startsWith("http://") &&
    !origin.includes("onrender.com")
  ) {
    return jsonError(
      503,
      "API_INTERNAL_URL must be the public https://…onrender.com URL. Free web services cannot call each other over Render’s private network.",
    );
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

  const method = request.method;
  const hasBody = !["GET", "HEAD"].includes(method);
  const body = hasBody ? await request.arrayBuffer() : undefined;

  let response: Response;
  try {
    response = await fetchApi(target, {
      method,
      headers,
      body,
      redirect: "manual",
      cache: "no-store",
    });
  } catch {
    return jsonError(
      503,
      "The API is starting or is unreachable. Wait about a minute and try again. Confirm API_INTERNAL_URL on the web service.",
    );
  }

  const payload = await response.arrayBuffer();
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
