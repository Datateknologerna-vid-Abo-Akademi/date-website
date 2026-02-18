import type { ApiError, ApiSuccess } from "./types";

function getCookie(name: string) {
  if (typeof document === "undefined") return "";
  const match = document.cookie.match(new RegExp(`(^| )${name}=([^;]+)`));
  return match ? decodeURIComponent(match[2]) : "";
}

async function ensureCsrfCookie() {
  await fetch("/api/v1/auth/session", {
    method: "GET",
    credentials: "include",
  });
}

interface ClientOptions {
  method: "POST" | "PATCH" | "DELETE";
  path: string;
  body?: unknown;
}

export async function getApiClient<T>(path: string): Promise<T> {
  const response = await fetch(`/api/v1/${path.replace(/^\//, "")}`, {
    method: "GET",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
    },
  });
  const payload = (await response.json()) as ApiSuccess<T> | ApiError;
  if (!response.ok || "error" in payload) {
    const message = "error" in payload ? payload.error.message : "Request failed";
    throw new Error(message);
  }
  return payload.data;
}

export async function mutateApi<T>({ method, path, body }: ClientOptions): Promise<T> {
  await ensureCsrfCookie();
  const csrfToken = getCookie("csrftoken");

  const response = await fetch(`/api/v1/${path.replace(/^\//, "")}`, {
    method,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": csrfToken,
    },
    body: body ? JSON.stringify(body) : undefined,
  });

  if (response.status === 204) return undefined as T;

  const payload = (await response.json()) as ApiSuccess<T> | ApiError;
  if (!response.ok || "error" in payload) {
    const message = "error" in payload ? payload.error.message : "Request failed";
    throw new Error(message);
  }
  return payload.data;
}
