import { headers } from "next/headers";

const PASSTHROUGH_HEADERS = [
  "content-type",
  "cache-control",
  "etag",
  "last-modified",
  "expires",
  "content-length",
];

async function resolveBackendOrigin() {
  if (process.env.BACKEND_API_ORIGIN) return process.env.BACKEND_API_ORIGIN;
  const incomingHeaders = await headers();
  const host = incomingHeaders.get("x-forwarded-host") ?? incomingHeaders.get("host");
  const proto = incomingHeaders.get("x-forwarded-proto") ?? "http";
  if (host) return `${proto}://${host}`;
  return "http://localhost:8000";
}

export async function proxyAssetPath(prefix: "/static" | "/media", path: string[]) {
  const backendOrigin = await resolveBackendOrigin();
  const normalized = path.map((segment) => encodeURIComponent(segment)).join("/");
  const targetUrl = `${backendOrigin}${prefix}/${normalized}`;
  const upstream = await fetch(targetUrl, { cache: "no-store" });

  const responseHeaders = new Headers();
  for (const header of PASSTHROUGH_HEADERS) {
    const value = upstream.headers.get(header);
    if (value) responseHeaders.set(header, value);
  }

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders,
  });
}
