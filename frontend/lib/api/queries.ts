import { fetchApi } from "./fetcher";
import type {
  EventItem,
  HomePayload,
  MemberProfile,
  NewsItem,
  PollQuestion,
  PublicFunctionaryPayload,
  SessionData,
  SiteMeta,
  StaticPage,
} from "./types";

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

export async function getSession() {
  return fetchApi<SessionData>("auth/session", { nextRevalidate: 0 });
}

export async function getMemberProfile() {
  return fetchApi<MemberProfile>("members/me", { nextRevalidate: 0 });
}

export async function getPublicFunctionaries(year?: string, role?: string) {
  const params = new URLSearchParams();
  if (year) params.set("year", year);
  if (role) params.set("role", role);
  const query = params.toString();
  return fetchApi<PublicFunctionaryPayload>(
    `members/functionaries${query ? `?${query}` : ""}`,
    { nextRevalidate: 60 },
  );
}

export async function getPolls() {
  return fetchApi<PollQuestion[]>("polls", { nextRevalidate: 60 });
}

export async function getPoll(pollId: number) {
  return fetchApi<PollQuestion>(`polls/${pollId}`, { nextRevalidate: 10 });
}
