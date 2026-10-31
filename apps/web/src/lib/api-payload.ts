export function readApiPayload(text: string, contentType: string, status: number): Record<string, unknown> {
  const trimmed = text.trim();
  const looksHtml =
    contentType.includes("text/html") ||
    trimmed.startsWith("<!") ||
    trimmed.toLowerCase().startsWith("<html");
  if (looksHtml) {
    throw new Error(
      status === 502 || status === 503 || status === 504
        ? "The API is starting. Wait about a minute and try again."
        : "The API returned a web page instead of JSON. On Render, set the web service API_INTERNAL_URL to the API’s public https://…onrender.com URL, then wait for a Free API to wake up.",
    );
  }
  if (trimmed && !contentType.includes("json") && trimmed.startsWith("<")) {
    throw new Error("The API returned a web page instead of JSON.");
  }
  let data: Record<string, unknown> = {};
  if (trimmed) {
    try {
      data = JSON.parse(text) as Record<string, unknown>;
    } catch {
      throw new Error(
        "The API returned an incomplete response. Wait about a minute for the Free API to wake up, then try again.",
      );
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
