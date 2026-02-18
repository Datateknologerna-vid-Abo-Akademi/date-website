import { fetchApi } from "./fetcher";
import type {
  ArchiveCollection,
  ArchiveDocumentsPayload,
  ArchiveExamDetailPayload,
  ArchivePictureDetailPayload,
  ArchiveYearsPayload,
  EventItem,
  HomePayload,
  MemberProfile,
  NewsItem,
  PaginatedPayload,
  PollQuestion,
  Publication,
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

export async function getArchiveYears() {
  return fetchApi<ArchiveYearsPayload>("archive/pictures/years", { nextRevalidate: 30 });
}

export async function getArchivePictureCollectionsByYear(year: number) {
  return fetchApi<ArchiveCollection[]>(`archive/pictures/${year}`, { nextRevalidate: 30 });
}

export async function getArchivePictureCollection(year: number, album: string, page = 1) {
  return fetchApi<ArchivePictureDetailPayload>(
    `archive/pictures/${year}/${encodeURIComponent(album)}?page=${page}`,
    { nextRevalidate: 10 },
  );
}

export async function getArchiveDocuments(collection?: string, titleContains?: string, page = 1) {
  const params = new URLSearchParams();
  params.set("page", String(page));
  if (collection) params.set("collection", collection);
  if (titleContains) params.set("title_contains", titleContains);
  return fetchApi<ArchiveDocumentsPayload>(`archive/documents?${params.toString()}`, { nextRevalidate: 10 });
}

export async function getArchiveExamCollections() {
  return fetchApi<ArchiveCollection[]>("archive/exams", { nextRevalidate: 30 });
}

export async function getArchiveExamCollection(collectionId: number, page = 1) {
  return fetchApi<ArchiveExamDetailPayload>(`archive/exams/${collectionId}?page=${page}`, { nextRevalidate: 10 });
}

export async function getPublications(page = 1) {
  return fetchApi<PaginatedPayload<Publication>>(`publications?page=${page}`, { nextRevalidate: 30 });
}

export async function getPublication(slug: string) {
  return fetchApi<Publication>(`publications/${slug}`, { nextRevalidate: 10 });
}
