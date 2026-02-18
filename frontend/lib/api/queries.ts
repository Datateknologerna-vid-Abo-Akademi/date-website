import { fetchApi } from "./fetcher";
import type {
  AdItem,
  ActivationPayload,
  AlumniUpdateTokenPayload,
  ArchiveCollection,
  ArchivePictureCollectionByIdPayload,
  ArchiveDocumentsPayload,
  ArchiveExamDetailPayload,
  ArchivePictureDetailPayload,
  ArchiveYearsPayload,
  CtfDetailPayload,
  CtfFlagDetailPayload,
  CtfItem,
  EventItem,
  EventAttendeeListPayload,
  HomePayload,
  LuciaCandidate,
  LuciaOverview,
  MemberProfile,
  NewsItem,
  PaginatedPayload,
  PollQuestion,
  Publication,
  PublicFunctionaryPayload,
  SocialOverview,
  SessionData,
  SiteMeta,
  StaticPage,
} from "./types";

export async function getSiteMeta() {
  return fetchApi<SiteMeta>("meta/site", { nextRevalidate: 0 });
}

export async function getHomeData() {
  return fetchApi<HomePayload>("home", { nextRevalidate: 120 });
}

export async function getNews(category?: string, author?: string) {
  const params = new URLSearchParams();
  if (category) params.set("category", category);
  if (author) params.set("author", author);
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

export async function getEventAttendees(slug: string) {
  return fetchApi<EventAttendeeListPayload>(`events/${slug}/attendees`, { nextRevalidate: 10 });
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

export async function getArchivePictureCollectionById(collectionId: number) {
  return fetchApi<ArchivePictureCollectionByIdPayload>(`archive/pictures/id/${collectionId}`, {
    nextRevalidate: 30,
  });
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

export async function getSocialOverview() {
  return fetchApi<SocialOverview>("social", { nextRevalidate: 300 });
}

export async function getAds() {
  return fetchApi<AdItem[]>("ads", { nextRevalidate: 300 });
}

export async function getCtfEvents() {
  return fetchApi<CtfItem[]>("ctf", { nextRevalidate: 10 });
}

export async function getCtfEvent(slug: string) {
  return fetchApi<CtfDetailPayload>(`ctf/${slug}`, { nextRevalidate: 10 });
}

export async function getCtfFlag(ctfSlug: string, flagSlug: string) {
  return fetchApi<CtfFlagDetailPayload>(`ctf/${ctfSlug}/${flagSlug}`, { nextRevalidate: 5 });
}

export async function getLuciaOverview() {
  return fetchApi<LuciaOverview>("lucia", { nextRevalidate: 300 });
}

export async function getLuciaCandidates() {
  return fetchApi<LuciaCandidate[]>("lucia/candidates", { nextRevalidate: 60 });
}

export async function getLuciaCandidate(slug: string) {
  return fetchApi<LuciaCandidate>(`lucia/candidates/${slug}`, { nextRevalidate: 30 });
}

export async function getAlumniUpdateToken(token: string) {
  return fetchApi<AlumniUpdateTokenPayload>(`alumni/update/${token}`, { nextRevalidate: 0 });
}

export async function activateAccount(uid: string, token: string) {
  return fetchApi<ActivationPayload>(`auth/activate/${uid}/${token}`, { nextRevalidate: 0 });
}
