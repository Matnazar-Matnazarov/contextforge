/**
 * Same-origin API client (Caddy routes /api/* to Django). Auth is a Django session cookie (HttpOnly);
 * nothing sensitive is stored in JS-accessible storage. Unsafe methods send the CSRF token.
 */

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.split("; ").find((c) => c.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.split("=")[1]) : null;
}

let csrfPromise: Promise<void> | null = null;
async function ensureCsrf(): Promise<string> {
  if (!readCookie("csrftoken")) {
    csrfPromise ??= fetch("/api/auth/csrf/", { credentials: "same-origin" })
      .then(() => undefined)
      .finally(() => {
        csrfPromise = null;
      });
    await csrfPromise;
  }
  return readCookie("csrftoken") ?? "";
}

async function toError(res: Response): Promise<ApiError> {
  let body: { error?: { code?: string; message?: string; details?: unknown } } = {};
  try {
    body = await res.json();
  } catch {
    /* non-JSON error body */
  }
  const e = body.error;
  return new ApiError(res.status, e?.code ?? "error", e?.message ?? `Request failed (${res.status})`, e?.details);
}

export async function api<T = unknown>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const method = (init.method ?? "GET").toUpperCase();
  const headers = new Headers(init.headers);
  let body = init.body;
  if (init.json !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(init.json);
  }
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    headers.set("X-CSRFToken", await ensureCsrf());
  }
  const res = await fetch(`/api${path}`, { ...init, method, headers, body, credentials: "same-origin" });
  if (!res.ok) throw await toError(res);
  if (res.status === 204 || res.status === 202) return undefined as T;
  return (await res.json()) as T;
}

/** Multipart upload with progress (fetch cannot report upload progress). */
export async function uploadFile<T>(path: string, file: File, onProgress?: (pct: number) => void): Promise<T> {
  const token = await ensureCsrf();
  return new Promise<T>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `/api${path}`);
    xhr.setRequestHeader("X-CSRFToken", token);
    xhr.withCredentials = true;
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress?.(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onerror = () => reject(new ApiError(0, "network", "Network error. Check your connection."));
    xhr.onload = () => {
      let parsed: { error?: { code?: string; message?: string } } & Record<string, unknown> = {};
      try {
        parsed = JSON.parse(xhr.responseText);
      } catch {
        /* ignore */
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(parsed as T);
      else reject(new ApiError(xhr.status, parsed.error?.code ?? "error", parsed.error?.message ?? "Upload failed."));
    };
    const form = new FormData();
    form.append("file", file);
    xhr.send(form);
  });
}

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    const d = err.details as Record<string, string[] | string> | undefined;
    if (err.code === "validation_error" && d && typeof d === "object") {
      const first = Object.values(d).flat()[0];
      if (typeof first === "string") return first;
    }
    return err.message;
  }
  return "Something went wrong. Please try again.";
}
