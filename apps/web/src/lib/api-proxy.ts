export const SELF_PROXY_MESSAGE =
  "API_INTERNAL_URL points at this web service. Set it to the API’s public https://…onrender.com URL, not the web or custom-domain URL.";

export const INVALID_HOST_MESSAGE =
  "The API rejected the Host header. On the API service, set DOCUFLOW_TRUSTED_HOSTS to .onrender.com and your custom domain (if any), then redeploy the API.";

export const MISSING_API_URL_MESSAGE =
  "The web service is missing API_INTERNAL_URL. Set it to your API’s public https://…onrender.com URL (not localhost).";

export const PRIVATE_NETWORK_MESSAGE =
  "API_INTERNAL_URL must be the public https://…onrender.com URL. Free web services cannot call each other over Render’s private network.";

export const API_UNREACHABLE_MESSAGE =
  "The API is starting or is unreachable. Wait about a minute and try again. Confirm API_INTERNAL_URL on the web service.";

export function apiOriginFromEnv(env: {
  API_INTERNAL_URL?: string;
  DOCUFLOW_PUBLIC_API_URL?: string;
}): string {
  const raw = (env.API_INTERNAL_URL || env.DOCUFLOW_PUBLIC_API_URL || "").trim();
  return raw.replace(/\/$/, "");
}

export function isLocalPlaceholder(url: string): boolean {
  return !url || /localhost|127\.0\.0\.1/.test(url);
}

export function isSelfProxy(apiUrl: string, incomingHost: string): boolean {
  if (!apiUrl || !incomingHost) return false;
  try {
    const apiHost = new URL(apiUrl).host.toLowerCase();
    const webHost = incomingHost.trim().toLowerCase();
    if (!webHost) return false;
    if (apiHost === webHost) return true;
    return apiHost.split(":")[0] === webHost.split(":")[0];
  } catch {
    return false;
  }
}

export function isBinaryContentType(contentType: string): boolean {
  const type = contentType.toLowerCase();
  return (
    type.includes("application/pdf") ||
    type.includes("application/zip") ||
    type.includes("octet-stream") ||
    type.startsWith("image/") ||
    type.startsWith("audio/") ||
    type.startsWith("video/")
  );
}

export function looksHtml(text: string, contentType: string): boolean {
  const trimmed = text.trim();
  const type = contentType.toLowerCase();
  return (
    type.includes("text/html") ||
    trimmed.startsWith("<!") ||
    trimmed.toLowerCase().startsWith("<html") ||
    /<head[\s>]|<body[\s>]/i.test(trimmed.slice(0, 240))
  );
}

export function looksInvalidHost(text: string): boolean {
  return text.trim().toLowerCase() === "invalid host header";
}

export function looksJsonObjectOrArray(text: string): boolean {
  const trimmed = text.trim();
  return trimmed.startsWith("{") || trimmed.startsWith("[");
}

export function isValidJson(text: string): boolean {
  if (!text.trim()) return false;
  try {
    JSON.parse(text);
    return true;
  } catch {
    return false;
  }
}

export function shouldRetryUpstream(status: number, text: string, contentType: string): boolean {
  if (looksInvalidHost(text)) return false;
  if (status === 502 || status === 503 || status === 504) return true;
  if (looksHtml(text, contentType)) return true;
  if (looksJsonObjectOrArray(text) && !isValidJson(text)) return true;
  return false;
}

export function sanitizePreview(text: string, limit = 80): string {
  return text.replace(/\s+/g, " ").trim().slice(0, limit);
}

export function messageForNonJsonBody(text: string, status: number, contentType: string): string {
  const trimmed = text.trim();
  if (looksInvalidHost(trimmed)) return INVALID_HOST_MESSAGE;
  if (looksHtml(trimmed, contentType) || trimmed.startsWith("<")) {
    return status === 502 || status === 503 || status === 504
      ? "The API is starting. Wait about a minute and try again."
      : "The API returned a web page instead of JSON. On Render, set the web service API_INTERNAL_URL to the API’s public https://…onrender.com URL, then wait for a Free API to wake up.";
  }
  if (looksJsonObjectOrArray(trimmed)) {
    return "The API returned an incomplete response. Wait about a minute for the Free API to wake up, then try again.";
  }
  const preview = sanitizePreview(trimmed);
  if (preview) {
    return `The API returned a non-JSON response (${status}). ${preview}`;
  }
  return "The API returned an empty response. Wait about a minute for the Free API to wake up, then try again.";
}
