import { type NextRequest } from "next/server";

const API = process.env.API_INTERNAL_URL || "http://127.0.0.1:43124";

async function proxy(request: NextRequest, path: string[]) {
  const target = `${API}/v1/${path.join("/")}${request.nextUrl.search}`;
  const headers = new Headers();
  const accept = request.headers.get("accept");
  const contentType = request.headers.get("content-type");
  const cookie = request.headers.get("cookie");
  const csrf = request.headers.get("x-csrf-token");
  const origin = request.headers.get("origin");
  if (accept) headers.set("accept", accept);
  if (contentType) headers.set("content-type", contentType);
  if (cookie) headers.set("cookie", cookie);
  if (csrf) headers.set("x-csrf-token", csrf);
  if (origin) headers.set("origin", origin);

  const method = request.method;
  const hasBody = !["GET", "HEAD"].includes(method);
  const body = hasBody ? await request.arrayBuffer() : undefined;
  const response = await fetch(target, {
    method,
    headers,
    body,
    redirect: "manual",
  });

  const outbound = new Headers();
  response.headers.forEach((value, key) => {
    if (["content-encoding", "transfer-encoding"].includes(key.toLowerCase())) return;
    if (key.toLowerCase() === "set-cookie") return;
    outbound.set(key, value);
  });
  const nextResponse = new Response(response.body, { status: response.status, headers: outbound });
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
