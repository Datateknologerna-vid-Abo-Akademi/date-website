import "server-only";

import { headers } from "next/headers";

import type { ApiError, ApiSuccess } from "./types";

interface RequestOptions extends RequestInit {
  nextRevalidate?: number;
}

async function getRequestOrigin() {
  if (process.env.BACKEND_API_ORIGIN) {
    return process.env.BACKEND_API_ORIGIN;
  }
  const incomingHeaders = await headers();
  const host = incomingHeaders.get("x-forwarded-host") ?? incomingHeaders.get("host");
  const protocol = incomingHeaders.get("x-forwarded-proto") ?? "http";
  if (host) return `${protocol}://${host}`;
  return process.env.NEXT_PUBLIC_APP_ORIGIN ?? "http://localhost:3000";
}

export async function fetchApi<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const incomingHeaders = await headers();
  const cookie = incomingHeaders.get("cookie");
  const origin = await getRequestOrigin();
  const url = `${origin}/api/v1/${path.replace(/^\//, "")}`;

  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(cookie ? { Cookie: cookie } : {}),
      ...(options.headers ?? {}),
    },
    next: options.nextRevalidate
      ? {
          revalidate: options.nextRevalidate,
        }
      : undefined,
    cache: options.nextRevalidate ? undefined : "no-store",
  });

  const payload = (await response.json()) as ApiSuccess<T> | ApiError;
  if (!response.ok || "error" in payload) {
    const message = "error" in payload ? payload.error.message : "Request failed";
    throw new Error(message);
  }
  return payload.data;
}
