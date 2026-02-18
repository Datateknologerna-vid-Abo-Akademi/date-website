import { fetchApi } from "./fetcher";
import type { EventItem, HomePayload, NewsItem, SiteMeta, StaticPage } from "./types";

export async function getSiteMeta() {
  return fetchApi<SiteMeta>("meta/site", { nextRevalidate: 300 });
}

export async function getHomeData() {
  return fetchApi<HomePayload>("home", { nextRevalidate: 120 });
}

export async function getNews(category?: string) {
  const params = new URLSearchParams();
  if (category) params.set("category", category);
  const query = params.toString();
  return fetchApi<NewsItem[]>(`news${query ? `?${query}` : ""}`, { nextRevalidate: 120 });
}

export async function getNewsArticle(slug: string, category?: string) {
  const params = new URLSearchParams();
  if (category) params.set("category", category);
  const query = params.toString();
  return fetchApi<NewsItem>(`news/${slug}${query ? `?${query}` : ""}`, { nextRevalidate: 120 });
}

export async function getEvents(includePast = false) {
  const query = includePast ? "?include_past=true" : "";
  return fetchApi<EventItem[]>(`events${query}`, { nextRevalidate: 120 });
}

export async function getEvent(slug: string) {
  return fetchApi<EventItem>(`events/${slug}`, { nextRevalidate: 60 });
}

export async function getStaticPage(slug: string) {
  return fetchApi<StaticPage>(`pages/${slug}`, { nextRevalidate: 300 });
}
