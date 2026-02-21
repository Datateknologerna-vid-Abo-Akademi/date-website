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
  const response = await fetch(url, init);

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

