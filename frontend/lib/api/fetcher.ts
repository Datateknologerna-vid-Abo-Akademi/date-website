import "server-only";

import { headers } from "next/headers";

import type { ApiError, ApiSuccess } from "./types";

interface RequestOptions extends RequestInit {
  nextRevalidate?: number;
}

export class ApiRequestError extends Error {
  readonly status: number;

  readonly code?: string;

  readonly details?: Record<string, unknown>;

  constructor(params: {
    message: string;
    status: number;
    code?: string;
    details?: Record<string, unknown>;
  }) {
    super(params.message);
    this.name = "ApiRequestError";
    this.status = params.status;
    this.code = params.code;
    this.details = params.details;
  }
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

  let payload: ApiSuccess<T> | ApiError | null = null;
  try {
    payload = (await response.json()) as ApiSuccess<T> | ApiError;
  } catch {
    payload = null;
  }

  if (!response.ok) {
    const errorPayload =
      payload && "error" in payload
        ? payload.error
        : undefined;
    throw new ApiRequestError({
      message: errorPayload?.message ?? `Request failed with status ${response.status}.`,
      status: response.status,
      code: errorPayload?.code,
      details: errorPayload?.details,
    });
  }

  if (!payload || "error" in payload) {
    throw new ApiRequestError({
      message: payload && "error" in payload ? payload.error.message : "Unexpected API response.",
      status: response.status,
      code: payload && "error" in payload ? payload.error.code : undefined,
      details: payload && "error" in payload ? payload.error.details : undefined,
    });
  }
  return payload.data;
}
