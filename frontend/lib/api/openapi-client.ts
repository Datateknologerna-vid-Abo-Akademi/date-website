import createClient from "openapi-fetch";
import type { paths } from "./schema";

export const getRequestOrigin = () => {
  if (typeof window !== "undefined") {
    // Relative URLs in browser are fine, or window.location.origin
    return "";
  }
  return process.env.BACKEND_API_ORIGIN ?? process.env.NEXT_PUBLIC_APP_ORIGIN ?? "http://localhost:3000";
};

interface ServerRequestContext {
  cookieHeader: string;
  tenantSlug: string;
  locale: string;
  forwardedHost: string;
  forwardedProto: string;
}

async function getServerRequestContext(): Promise<ServerRequestContext | null> {
  if (typeof window !== "undefined") return null;

  const { headers } = await import("next/headers");
  const incomingHeaders = await headers();

  return {
    cookieHeader: incomingHeaders.get("cookie") ?? "",
    tenantSlug: incomingHeaders.get("x-tenant-slug") ?? "",
    locale: incomingHeaders.get("x-locale") ?? "",
    forwardedHost:
      incomingHeaders.get("x-forwarded-host") ?? incomingHeaders.get("host") ?? "",
    forwardedProto: incomingHeaders.get("x-forwarded-proto") ?? "http",
  };
}

function hasAuthModeSession(headers: HeadersInit | undefined): boolean {
  if (!headers) return false;
  const normalized = new Headers(headers);
  return normalized.get("X-Auth-Mode")?.toLowerCase() === "session";
}

// Custom fetch to unwrap Django's { "data": ... } response
const unwrapDjangoResponse = async (url: RequestInfo | URL, init?: RequestInit) => {
  const method = init?.method?.toUpperCase() ?? "GET";

  const newInit: RequestInit = {
    ...init,
    credentials: "include", // Ensure session cookies are sent
  };

  const serverContext = await getServerRequestContext();
  if (serverContext) {
    const mergedHeaders = new Headers(newInit.headers);

    if (serverContext.cookieHeader) {
      mergedHeaders.set("Cookie", serverContext.cookieHeader);
      // Any request carrying user cookies must bypass fetch cache to avoid response bleed.
      newInit.cache = "no-store";
      (newInit as RequestInit & { next?: { revalidate?: number } }).next = { revalidate: 0 };
    }

    if (serverContext.tenantSlug) mergedHeaders.set("X-Tenant-Slug", serverContext.tenantSlug);
    if (serverContext.locale) mergedHeaders.set("X-Locale", serverContext.locale);
    if (serverContext.locale) mergedHeaders.set("Accept-Language", serverContext.locale);
    if (serverContext.forwardedHost) mergedHeaders.set("X-Forwarded-Host", serverContext.forwardedHost);
    if (serverContext.forwardedProto) mergedHeaders.set("X-Forwarded-Proto", serverContext.forwardedProto);

    newInit.headers = mergedHeaders;
  }

  if (hasAuthModeSession(newInit.headers)) {
    newInit.cache = "no-store";
    (newInit as RequestInit & { next?: { revalidate?: number } }).next = { revalidate: 0 };
  }

  // Attach CSRF tokens for mutations in the browser
  if (["POST", "PUT", "PATCH", "DELETE"].includes(method) && typeof document !== "undefined") {
    // Ensure the browser has a valid session cookie for CSRF
    await fetch("/api/v1/auth/session", { method: "GET", credentials: "include" });
    const match = document.cookie.match(/(^| )csrftoken=([^;]+)/);
    const csrfToken = match ? decodeURIComponent(match[2]) : "";
    if (csrfToken) {
      newInit.headers = {
        ...newInit.headers,
        "X-CSRFToken": csrfToken,
      };
    }
  }

  const response = await fetch(url, newInit);

  if (response.status === 204) {
    return response;
  }

  try {
    const json = await response.json();
    if (response.ok && json.data !== undefined) {
      // Create a fake response with the unwrapped data so openapi-fetch parses it correctly
      return new Response(JSON.stringify(json.data), {
        status: response.status,
        statusText: response.statusText,
        headers: response.headers,
      });
    }
    if (!response.ok && json.error !== undefined) {
      return new Response(JSON.stringify(json.error), {
        status: response.status,
        statusText: response.statusText,
        headers: response.headers,
      });
    }
    // Fallback
    return new Response(JSON.stringify(json), {
      status: response.status,
      statusText: response.statusText,
      headers: response.headers,
    });
  } catch {
    return response; // Not JSON probably
  }
};
export const apiClient = createClient<paths>({
  baseUrl: `${getRequestOrigin()}`,
  fetch: unwrapDjangoResponse,
});

