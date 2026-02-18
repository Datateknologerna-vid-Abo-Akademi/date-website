import type { NextRequest } from "next/server";

export async function GET(request: NextRequest) {
  const feedUrl = new URL("/api/v1/news/feed", request.url);
  const response = await fetch(feedUrl, { cache: "no-store" });
  const contentType = response.headers.get("content-type") ?? "application/rss+xml; charset=utf-8";

  return new Response(response.body, {
    status: response.status,
    headers: {
      "content-type": contentType,
      "cache-control": "public, max-age=300",
    },
  });
}
