import createClient from "openapi-fetch";
import type { paths } from "./schema";

export const getRequestOrigin = () => {
  if (typeof window !== "undefined") {
    // Relative URLs in browser are fine, or window.location.origin
    return "";
  }
  return process.env.BACKEND_API_ORIGIN ?? process.env.NEXT_PUBLIC_APP_ORIGIN ?? "http://localhost:3000";
};

// Custom fetch to unwrap Django's { "data": ... } response
const unwrapDjangoResponse = async (url: RequestInfo | URL, init?: RequestInit) => {
  const method = init?.method?.toUpperCase() ?? "GET";

  const newInit: RequestInit = {
    ...init,
    credentials: "include", // Ensure session cookies are sent
  };

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

