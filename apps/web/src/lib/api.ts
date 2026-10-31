import { readApiPayload } from "./api-payload";

export type User = {
  id: string;
  email: string;
  name: string;
  role: string;
  plan_slug: string;
  email_verified: boolean;
  credits_available: number;
  credits_balance: number;
  credits_reserved: number;
};

export type DocumentRecord = {
  id: string;
  original_filename: string;
  content_type: string;
  kind: string;
  byte_size: number;
  page_count: number | null;
  origin: string;
  expires_at: string;
  created_at: string | null;
};

export type JobRecord = {
  id: string;
  operation: string;
  status: string;
  progress: number;
  params: Record<string, unknown>;
  input_document_ids: string[];
  result_document_ids: string[];
  result_payload: Record<string, unknown>;
  error_code: string | null;
  error_message: string | null;
  credits_reserved: number;
  created_at: string | null;
  completed_at: string | null;
};

function csrfToken() {
  if (typeof document === "undefined") return "";
  const match = document.cookie.split("; ").find((row) => row.startsWith("df_csrf="));
  return match ? decodeURIComponent(match.split("=")[1] ?? "") : "";
}

async function parse(response: Response) {
  const text = await response.text();
  return readApiPayload(text, response.headers.get("content-type") || "", response.status);
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (!(init.body instanceof FormData) && !headers.has("Content-Type") && init.body) {
    headers.set("Content-Type", "application/json");
  }
  const csrf = csrfToken();
  if (csrf && !headers.has("X-CSRF-Token")) {
    headers.set("X-CSRF-Token", csrf);
  }
  const response = await fetch(path, { ...init, headers, credentials: "include" });
  return parse(response) as Promise<T>;
}

export const Auth = {
  me: () => api<User>("/v1/auth/me"),
  register: (body: { email: string; password: string; name: string }) =>
    api<User>("/v1/auth/register", { method: "POST", body: JSON.stringify(body) }),
  login: (body: { email: string; password: string }) =>
    api<User>("/v1/auth/login", { method: "POST", body: JSON.stringify(body) }),
  logout: () => api<{ ok: boolean }>("/v1/auth/logout", { method: "POST" }),
  forgot: (email: string) =>
    api<{ ok: boolean }>("/v1/auth/forgot-password", { method: "POST", body: JSON.stringify({ email }) }),
  reset: (token: string, password: string) =>
    api<{ ok: boolean }>("/v1/auth/reset-password", { method: "POST", body: JSON.stringify({ token, password }) }),
  verify: (token: string) =>
    api<{ ok: boolean }>("/v1/auth/verify-email", { method: "POST", body: JSON.stringify({ token }) }),
  updateName: (name: string) =>
    api<User>("/v1/auth/me", { method: "PATCH", body: JSON.stringify({ name }) }),
  deleteAccount: () => api<{ ok: boolean }>("/v1/auth/me", { method: "DELETE" }),
};

export const Docs = {
  list: () => api<DocumentRecord[]>("/v1/documents"),
  upload: async (file: File) => {
    const body = new FormData();
    body.append("file", file);
    return api<DocumentRecord>("/v1/documents", { method: "POST", body });
  },
  remove: (id: string) => api<{ ok: boolean }>(`/v1/documents/${id}`, { method: "DELETE" }),
  downloadUrl: (id: string) => `/v1/documents/${id}/download`,
};

export const Jobs = {
  list: () => api<JobRecord[]>("/v1/jobs"),
  get: (id: string) => api<JobRecord>(`/v1/jobs/${id}`),
  create: (body: {
    operation: string;
    document_ids: string[];
    params?: Record<string, unknown>;
    idempotency_key?: string;
  }) => api<JobRecord>("/v1/jobs", { method: "POST", body: JSON.stringify(body) }),
  cancel: (id: string) => api<JobRecord>(`/v1/jobs/${id}/cancel`, { method: "POST" }),
};

export const Billing = {
  plans: () => api<Array<Record<string, unknown>>>("/v1/billing/plans"),
  usage: () => api<Record<string, unknown>>("/v1/billing/usage"),
  ledger: () => api<Array<Record<string, unknown>>>("/v1/billing/ledger"),
};

export const Meta = {
  tools: () => api<Record<string, unknown>>("/v1/meta/tools"),
};

export const Admin = {
  overview: () => api<Record<string, unknown>>("/v1/admin/overview"),
  users: () => api<Array<Record<string, unknown>>>("/v1/admin/users"),
  jobs: () => api<Array<Record<string, unknown>>>("/v1/admin/jobs"),
};
