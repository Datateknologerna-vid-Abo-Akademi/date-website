export class ApiRequestError extends Error {
  public status: number;
  public code?: string;
  public details?: Record<string, unknown>;

  constructor({
    message,
    status,
    code,
    details,
  }: {
    message: string;
    status: number;
    code?: string;
    details?: Record<string, unknown>;
  }) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}
import { apiClient } from "./openapi-client";
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

type ApiErrorPayload = {
  message?: string;
  details?: Record<string, unknown>;
  code?: string;
};

function isApiErrorPayload(value: unknown): value is ApiErrorPayload {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const candidate = value as Record<string, unknown>;
  const validMessage = candidate.message === undefined || typeof candidate.message === "string";
  const validDetails = candidate.details === undefined || (typeof candidate.details === "object" && candidate.details !== null);
  const validCode = candidate.code === undefined || typeof candidate.code === "string";
  return validMessage && validDetails && validCode;
}

// Helper to unwrap standard openapi-fetch { data, error } responses
// It assumes they have already been unwrapped from Django's {"data": ...} by openapi-client fetch wrapper.
async function unwrap<T>(promise: Promise<{ data?: T; error?: unknown }>): Promise<T> {
  const { data, error } = await promise;
  if (error) {
    const parsedError = isApiErrorPayload(error) ? error : {};
    throw new ApiRequestError({
      message: parsedError.message || "API Error",
      status: 400,
      details: parsedError.details,
      code: parsedError.code,
    });
  }
  if (!data) throw new Error("No data returned");
  return data;
}

const SESSION_REQUEST_OPTIONS = {
  cache: "no-store" as const,
  next: { revalidate: 0 },
  headers: {
    "X-Auth-Mode": "session",
  },
};

export async function getSiteMeta(): Promise<SiteMeta> {
  const data = await unwrap(apiClient.GET("/api/v1/meta/site", { cache: "no-store", next: { revalidate: 0 } }));
  return data as unknown as SiteMeta;
}

export async function getHomeData(): Promise<HomePayload> {
  const data = await unwrap(apiClient.GET("/api/v1/home", { cache: "no-store", next: { revalidate: 0 } }));
  return data as unknown as HomePayload;
}

export async function getNews(category?: string, author?: string) {
  const data = await unwrap(
    apiClient.GET("/api/v1/news", {
      // @ts-expect-error fallback query
      params: { query: { category, author } },
      next: { revalidate: 120 },
    }),
  );
  return data as unknown as NewsItem[];
}

export async function getNewsArticle(slug: string, category?: string) {
  const data = await unwrap(
    apiClient.GET("/api/v1/news/{slug}", {
      // @ts-expect-error fallback query
      params: { path: { slug }, query: { category } },
      next: { revalidate: 120 },
    }),
  );
  return data as unknown as NewsItem;
}

export async function getEvents(includePast = false): Promise<EventItem[]> {
  const includePastQuery = includePast ? "true" : "false";
  const data = await unwrap(
    apiClient.GET("/api/v1/events", {
      // @ts-expect-error fallback query
      params: { query: { include_past: includePastQuery } },
      next: { revalidate: 120 },
    }),
  );
  return data as unknown as EventItem[];
}

export async function getEvent(slug: string) {
  const data = await unwrap(
    apiClient.GET("/api/v1/events/{slug}", {
      params: { path: { slug } },
      next: { revalidate: 60 },
    }),
  );
  return data as unknown as EventItem;
}

export async function getEventAttendees(slug: string) {
  const data = await unwrap(
    apiClient.GET("/api/v1/events/{slug}/attendees", {
      params: { path: { slug } },
      next: { revalidate: 10 },
    }),
  );
  return data as unknown as EventAttendeeListPayload;
}

export async function getStaticPage(slug: string) {
  const data = await unwrap(
    apiClient.GET("/api/v1/pages/{slug}", {
      params: { path: { slug } },
      next: { revalidate: 300 },
    }),
  );
  return data as unknown as StaticPage;
}

export async function getSession() {
  const data = await unwrap(apiClient.GET("/api/v1/auth/session", SESSION_REQUEST_OPTIONS));
  return data as unknown as SessionData;
}

export async function getMemberProfile() {
  const data = await unwrap(apiClient.GET("/api/v1/members/me", SESSION_REQUEST_OPTIONS));
  return data as unknown as MemberProfile;
}

export async function getPublicFunctionaries(year?: string, role?: string) {
  const data = await unwrap(
    apiClient.GET("/api/v1/members/functionaries", {
      // @ts-expect-error fallback query
      params: { query: { year, role } },
      next: { revalidate: 60 },
    }),
  );
  return data as unknown as PublicFunctionaryPayload;
}

export async function getPolls() {
  const data = await unwrap(apiClient.GET("/api/v1/polls", { next: { revalidate: 60 } }));
  return data as unknown as PollQuestion[];
}

export async function getPoll(pollId: number) {
  const data = await unwrap(
    apiClient.GET("/api/v1/polls/{poll_id}", {
      params: { path: { poll_id: pollId } },
      next: { revalidate: 10 },
    }),
  );
  return data as unknown as PollQuestion;
}

export async function getArchiveYears() {
  const data = await unwrap(apiClient.GET("/api/v1/archive/pictures/years", SESSION_REQUEST_OPTIONS));
  return data as unknown as ArchiveYearsPayload;
}

export async function getArchivePictureCollectionsByYear(year: number) {
  const data = await unwrap(
    apiClient.GET("/api/v1/archive/pictures/{year}", {
      params: { path: { year } },
      ...SESSION_REQUEST_OPTIONS,
    }),
  );
  return data as unknown as ArchiveCollection[];
}

export async function getArchivePictureCollection(year: number, album: string, page = 1) {
  const data = await unwrap(
    apiClient.GET("/api/v1/archive/pictures/{year}/{album}", {
      // @ts-expect-error fallback query
      params: { path: { year, album }, query: { page } },
      ...SESSION_REQUEST_OPTIONS,
    }),
  );
  return data as unknown as ArchivePictureDetailPayload;
}

export async function getArchivePictureCollectionById(collectionId: number) {
  const data = await unwrap(
    apiClient.GET("/api/v1/archive/pictures/id/{collection_id}", {
      params: { path: { collection_id: collectionId } },
      ...SESSION_REQUEST_OPTIONS,
    }),
  );
  return data as unknown as ArchivePictureCollectionByIdPayload;
}

export async function getArchiveDocuments(collection?: string, titleContains?: string, page = 1) {
  const data = await unwrap(
    apiClient.GET("/api/v1/archive/documents", {
      // @ts-expect-error fallback query
      params: { query: { page, collection, title_contains: titleContains } },
      ...SESSION_REQUEST_OPTIONS,
    }),
  );
  return data as unknown as ArchiveDocumentsPayload;
}

export async function getArchiveExamCollections() {
  const data = await unwrap(apiClient.GET("/api/v1/archive/exams", SESSION_REQUEST_OPTIONS));
  return data as unknown as ArchiveCollection[];
}

export async function getArchiveExamCollection(collectionId: number, page = 1) {
  const data = await unwrap(
    apiClient.GET("/api/v1/archive/exams/{collection_id}", {
      // @ts-expect-error fallback query if needed
      params: { path: { collection_id: collectionId }, query: { page } },
      ...SESSION_REQUEST_OPTIONS,
    }),
  );
  return data as unknown as ArchiveExamDetailPayload;
}

export async function getPublications(page = 1) {
  const data = await unwrap(
    apiClient.GET("/api/v1/publications", {
      // @ts-expect-error fallback query
      params: { query: { page } },
      next: { revalidate: 30 },
    }),
  );
  return data as unknown as PaginatedPayload<Publication>;
}

export async function getPublication(slug: string) {
  const data = await unwrap(
    apiClient.GET("/api/v1/publications/{slug}", {
      params: { path: { slug } },
      next: { revalidate: 10 },
    }),
  );
  return data as unknown as Publication;
}

export async function getSocialOverview() {
  const data = await unwrap(apiClient.GET("/api/v1/social", { next: { revalidate: 300 } }));
  return data as unknown as SocialOverview;
}

export async function getAds() {
  const data = await unwrap(apiClient.GET("/api/v1/ads", { next: { revalidate: 300 } }));
  return data as unknown as AdItem[];
}

export async function getCtfEvents() {
  const data = await unwrap(apiClient.GET("/api/v1/ctf", SESSION_REQUEST_OPTIONS));
  return data as unknown as CtfItem[];
}

export async function getCtfEvent(slug: string) {
  const data = await unwrap(
    apiClient.GET("/api/v1/ctf/{slug}", {
      params: { path: { slug } },
      ...SESSION_REQUEST_OPTIONS,
    }),
  );
  return data as unknown as CtfDetailPayload;
}

export async function getCtfFlag(ctfSlug: string, flagSlug: string) {
  const data = await unwrap(
    apiClient.GET("/api/v1/ctf/{ctf_slug}/{flag_slug}", {
      params: { path: { ctf_slug: ctfSlug, flag_slug: flagSlug } },
      ...SESSION_REQUEST_OPTIONS,
    }),
  );
  return data as unknown as CtfFlagDetailPayload;
}

export async function getLuciaOverview() {
  const data = await unwrap(apiClient.GET("/api/v1/lucia", { next: { revalidate: 300 } }));
  return data as unknown as LuciaOverview;
}

export async function getLuciaCandidates() {
  const data = await unwrap(apiClient.GET("/api/v1/lucia/candidates", SESSION_REQUEST_OPTIONS));
  return data as unknown as LuciaCandidate[];
}

export async function getLuciaCandidate(slug: string) {
  const data = await unwrap(
    apiClient.GET("/api/v1/lucia/candidates/{slug}", {
      params: { path: { slug } },
      ...SESSION_REQUEST_OPTIONS,
    }),
  );
  return data as unknown as LuciaCandidate;
}

export async function getAlumniUpdateToken(token: string) {
  const data = await unwrap(
    apiClient.GET("/api/v1/alumni/update/{token}", {
      params: { path: { token } },
      next: { revalidate: 0 },
    }),
  );
  return data as unknown as AlumniUpdateTokenPayload;
}

export async function activateAccount(uid: string, token: string) {
  const data = await unwrap(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    apiClient.GET(`/api/v1/auth/activate/${uid}/${token}` as any, {
      next: { revalidate: 0 },
    }),
  );
  return data as unknown as ActivationPayload;
}
