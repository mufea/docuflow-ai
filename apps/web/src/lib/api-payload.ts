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
  const data = trimmed ? (JSON.parse(text) as Record<string, unknown>) : {};
  if (status < 200 || status >= 300) {
    const message = data.message || data.detail || `Request failed (${status})`;
    throw new Error(typeof message === "string" ? message : "Request failed");
  }
  return data;
}
