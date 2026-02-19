import { expect, type APIRequestContext, type Page } from "@playwright/test";

export type AuthMode = "anon" | "member";
export type EventVariant = "default" | "arsfest" | "baal" | "kk100" | "tomtejakt" | "wappmiddag";

export const REQUIRED_EVENT_VARIANTS: readonly EventVariant[] = [
  "default",
  "arsfest",
  "baal",
  "kk100",
  "tomtejakt",
  "wappmiddag",
] as const;

type ApiEnvelope<T> = {
  data?: T;
};

type ModuleCapability = {
  enabled?: boolean;
  nav_route?: string;
  routes?: string[];
};

type SiteMeta = {
  project_name?: string;
  association_theme?: {
    brand?: string;
  };
  navigation?: Array<{
    use_category_url?: boolean;
    url?: string;
    urls?: Array<{
      url?: string;
      logged_in_only?: boolean;
    }>;
  }>;
  module_capabilities?: Record<string, ModuleCapability>;
  default_landing_path?: string;
};

type EventsListItem = {
  slug: string;
  title: string;
};

type EventDetailItem = {
  slug: string;
  title: string;
  template_variant?: EventVariant;
  variant_sections?: Array<{
    slug: string;
  }>;
};

type NewsItem = {
  slug: string;
};

type PublicationItem = {
  slug: string;
};

type CtfItem = {
  slug: string;
};

type CtfDetailPayload = {
  flags?: Array<{
    slug: string;
  }>;
};

type LuciaCandidate = {
  slug: string;
};

type PollItem = {
  id: number;
};

type ArchiveYearsPayload = {
  year_albums?: Record<string, number>;
};

type ArchiveCollection = {
  id: number;
};

type ArchivePictureById = {
  year?: number;
  album?: string;
};

export type ManifestRoute = {
  path: string;
  source: string;
  requiresAuth: boolean;
};

type CrawlQueueItem = {
  path: string;
  depth: number;
};

export type ManifestResult = {
  routes: ManifestRoute[];
  missingVariants: EventVariant[];
  eventVariantBySlug: Record<string, EventVariant>;
};

type RouteChunkDefinition = {
  exact?: readonly string[];
  prefixes?: readonly string[];
};

export type BuildManifestOptions = {
  authMode: AuthMode;
  crawlEnabled: boolean;
  maxDepth: number;
  maxPages: number;
};

const ROOT_URL = "http://localhost";

const EXCLUDED_PATH_PREFIXES = [
  "/api/",
  "/admin",
  "/healthz",
  "/_next",
  "/media/",
  "/static/",
  "/events/feed",
  "/news/feed",
];

const EXCLUDED_PATH_EXACT = new Set([
  "/favicon.ico",
  "/robots.txt",
  "/sitemap.xml",
  "/members/logout",
]);

const MEMBER_REQUIRED_PREFIXES = [
  "/members/profile",
  "/members/info",
  "/members/funktionar",
  "/members/funktionarer",
  "/members/functionaries",
  "/members/cert",
];

const LEGACY_TITLE_VARIANTS: Record<string, EventVariant> = {
  "årsfest": "arsfest",
  "årsfest 2026": "arsfest",
  "årsfest gäster": "arsfest",
  "100 baal": "kk100",
  baal: "baal",
  tomtejakt: "tomtejakt",
  wappmiddag: "wappmiddag",
};

const LEGACY_SLUG_VARIANTS: Record<string, EventVariant> = {
  baal: "baal",
  tomtejakt: "tomtejakt",
  wappmiddag: "wappmiddag",
  arsfest: "arsfest",
  arsfest_stipendiater: "arsfest",
  arsfest26: "arsfest",
  on100_main: "arsfest",
  on100_student: "arsfest",
  on100_alumn: "arsfest",
  on100_guest: "arsfest",
  on100_secret: "arsfest",
  on100_stippe: "arsfest",
};

const ROUTE_CHUNKS: Record<string, RouteChunkDefinition> = {
  core: {
    exact: ["/"],
    prefixes: ["/events", "/members/login", "/news"],
  },
  home: {
    exact: ["/"],
  },
  events: {
    prefixes: ["/events"],
  },
  members: {
    prefixes: ["/members"],
  },
  "members-auth": {
    prefixes: ["/members/login", "/members/signup", "/members/password_reset", "/members/reset"],
  },
  news: {
    prefixes: ["/news"],
  },
  pages: {
    prefixes: ["/pages"],
  },
  social: {
    prefixes: ["/social"],
  },
  alumni: {
    prefixes: ["/alumni"],
  },
  archive: {
    prefixes: ["/archive"],
  },
  publications: {
    prefixes: ["/publications"],
  },
  polls: {
    prefixes: ["/polls"],
  },
  ctf: {
    prefixes: ["/ctf"],
  },
  lucia: {
    prefixes: ["/lucia"],
  },
  ads: {
    prefixes: ["/ads"],
  },
};

async function fetchApiData<T>(request: APIRequestContext, path: string): Promise<T | null> {
  const response = await request.get(path);
  if (!response.ok()) return null;
  const payload = (await response.json()) as ApiEnvelope<T>;
  return payload.data ?? null;
}

function normalizeEventHash(hash: string) {
  const value = hash.trim().toLowerCase();
  if (!value) return "";
  if (!value.startsWith("#")) return "";
  const normalized = value.replace(/^#\/?/, "");
  if (!normalized) return "";
  return `#/${normalized}`;
}

function normalizePath(candidate: string, baseOrigin: string) {
  const trimmed = candidate.trim();
  if (!trimmed) return null;
  if (trimmed.startsWith("mailto:") || trimmed.startsWith("tel:") || trimmed.startsWith("javascript:")) {
    return null;
  }

  let parsed: URL;
  try {
    parsed = new URL(trimmed, `${baseOrigin}/`);
  } catch {
    return null;
  }

  if (parsed.origin !== baseOrigin) return null;

  let pathname = parsed.pathname || "/";
  pathname = pathname.replace(/\/{2,}/g, "/");
  if (pathname.length > 1 && pathname.endsWith("/")) {
    pathname = pathname.slice(0, -1);
  }

  const hash = pathname.startsWith("/events/") ? normalizeEventHash(parsed.hash) : "";
  return `${pathname}${hash}`;
}

function shouldExclude(path: string) {
  const hashIndex = path.indexOf("#");
  const pathname = hashIndex === -1 ? path : path.slice(0, hashIndex);
  if (EXCLUDED_PATH_EXACT.has(pathname)) return true;
  return EXCLUDED_PATH_PREFIXES.some((prefix) => pathname.startsWith(prefix));
}

function inferRequiresAuth(path: string) {
  const hashIndex = path.indexOf("#");
  const pathname = hashIndex === -1 ? path : path.slice(0, hashIndex);
  return MEMBER_REQUIRED_PREFIXES.some((prefix) => pathname.startsWith(prefix));
}

function routeSortKey(route: ManifestRoute) {
  return `${route.path}|${route.requiresAuth ? "member" : "anon"}`;
}

function stripHash(path: string) {
  const hashIndex = path.indexOf("#");
  return hashIndex === -1 ? path : path.slice(0, hashIndex);
}

function upsertRoute(routeMap: Map<string, ManifestRoute>, route: ManifestRoute) {
  if (!route.path.startsWith("/")) return;
  if (shouldExclude(route.path)) return;
  const current = routeMap.get(route.path);
  if (!current) {
    routeMap.set(route.path, route);
    return;
  }
  if (!current.requiresAuth && route.requiresAuth) {
    routeMap.set(route.path, route);
  }
}

function resolveLegacyVariantByTitleAndSlug(title: string, slug: string): EventVariant {
  const titleKey = title.trim().toLowerCase();
  if (titleKey in LEGACY_TITLE_VARIANTS) {
    return LEGACY_TITLE_VARIANTS[titleKey];
  }
  if (slug in LEGACY_SLUG_VARIANTS) {
    return LEGACY_SLUG_VARIANTS[slug];
  }
  return "default";
}

async function expandDynamicRoutes(
  request: APIRequestContext,
  routeMap: Map<string, ManifestRoute>,
) {
  const eventVariantBySlug: Record<string, EventVariant> = {};
  const events = (await fetchApiData<EventsListItem[]>(request, "/api/v1/events?include_past=true")) ?? [];
  for (const event of events) {
    const eventPath = `/events/${event.slug}`;
    upsertRoute(routeMap, { path: eventPath, source: "api:events", requiresAuth: false });
    const detail = await fetchApiData<EventDetailItem>(request, `/api/v1/events/${event.slug}`);
    const variant = detail?.template_variant ?? "default";
    eventVariantBySlug[event.slug] = variant;
    if (variant !== "default") {
      upsertRoute(routeMap, { path: `${eventPath}#/main`, source: "api:events:variant", requiresAuth: false });
      upsertRoute(routeMap, { path: `${eventPath}#/anmalan`, source: "api:events:variant", requiresAuth: false });
      upsertRoute(routeMap, {
        path: `${eventPath}#/attendee-list`,
        source: "api:events:variant",
        requiresAuth: false,
      });
    }
    for (const section of detail?.variant_sections ?? []) {
      const sectionSlug = section.slug?.trim();
      if (!sectionSlug) continue;
      upsertRoute(routeMap, {
        path: `${eventPath}#/${sectionSlug}`,
        source: "api:events:variant-section",
        requiresAuth: false,
      });
    }
  }

  const news = (await fetchApiData<NewsItem[]>(request, "/api/v1/news")) ?? [];
  for (const item of news) {
    upsertRoute(routeMap, { path: `/news/${item.slug}`, source: "api:news", requiresAuth: false });
    upsertRoute(routeMap, { path: `/news/articles/${item.slug}`, source: "api:news:legacy-route", requiresAuth: false });
  }

  const publications =
    (await fetchApiData<{ results?: PublicationItem[] }>(request, "/api/v1/publications?page=1"))?.results ?? [];
  for (const item of publications) {
    upsertRoute(routeMap, { path: `/publications/${item.slug}`, source: "api:publications", requiresAuth: false });
  }

  const ctfEvents = (await fetchApiData<CtfItem[]>(request, "/api/v1/ctf")) ?? [];
  for (const ctf of ctfEvents) {
    upsertRoute(routeMap, { path: `/ctf/${ctf.slug}`, source: "api:ctf", requiresAuth: false });
    const detail = await fetchApiData<CtfDetailPayload>(request, `/api/v1/ctf/${ctf.slug}`);
    for (const flag of detail?.flags ?? []) {
      upsertRoute(routeMap, {
        path: `/ctf/${ctf.slug}/${flag.slug}`,
        source: "api:ctf:flag",
        requiresAuth: false,
      });
    }
  }

  const luciaCandidates = (await fetchApiData<LuciaCandidate[]>(request, "/api/v1/lucia/candidates")) ?? [];
  for (const candidate of luciaCandidates) {
    upsertRoute(routeMap, {
      path: `/lucia/candidates/${candidate.slug}`,
      source: "api:lucia",
      requiresAuth: false,
    });
  }

  const polls = (await fetchApiData<PollItem[]>(request, "/api/v1/polls")) ?? [];
  for (const poll of polls) {
    upsertRoute(routeMap, { path: `/polls/${poll.id}`, source: "api:polls", requiresAuth: false });
  }

  const archiveYears = (await fetchApiData<ArchiveYearsPayload>(request, "/api/v1/archive/pictures/years")) ?? {};
  const years = Object.keys(archiveYears.year_albums ?? {});
  for (const year of years) {
    const parsedYear = Number(year);
    if (!Number.isFinite(parsedYear)) continue;
    upsertRoute(routeMap, { path: `/archive/pictures/${parsedYear}`, source: "api:archive", requiresAuth: false });
    const yearCollections =
      (await fetchApiData<ArchiveCollection[]>(request, `/api/v1/archive/pictures/${parsedYear}`)) ?? [];
    for (const collection of yearCollections) {
      const byId = await fetchApiData<ArchivePictureById>(
        request,
        `/api/v1/archive/pictures/id/${collection.id}`,
      );
      if (byId?.year && byId?.album) {
        upsertRoute(routeMap, {
          path: `/archive/pictures/${byId.year}/${encodeURIComponent(byId.album)}`,
          source: "api:archive:album",
          requiresAuth: false,
        });
      }
    }
  }

  const examCollections = (await fetchApiData<ArchiveCollection[]>(request, "/api/v1/archive/exams")) ?? [];
  for (const collection of examCollections) {
    upsertRoute(routeMap, {
      path: `/archive/exams/${collection.id}`,
      source: "api:archive:exams",
      requiresAuth: false,
    });
  }

  return eventVariantBySlug;
}

async function getSiteMetaData(request: APIRequestContext) {
  const response = await request.get("/api/v1/meta/site");
  expect(response.ok()).toBeTruthy();
  const payload = (await response.json()) as ApiEnvelope<SiteMeta>;
  return payload.data ?? {};
}

function buildSeedRoutes(meta: SiteMeta) {
  const routeMap = new Map<string, ManifestRoute>();
  const landingPath = meta.default_landing_path ?? "/";
  upsertRoute(routeMap, { path: "/", source: "seed:root", requiresAuth: false });
  upsertRoute(routeMap, { path: landingPath, source: "seed:default-landing", requiresAuth: false });

  for (const capability of Object.values(meta.module_capabilities ?? {})) {
    if (!capability?.enabled) continue;
    if (capability.nav_route) {
      upsertRoute(routeMap, { path: capability.nav_route, source: "meta:module-nav", requiresAuth: false });
    }
    for (const route of capability.routes ?? []) {
      if (route.includes("{")) continue;
      upsertRoute(routeMap, { path: route, source: "meta:module-route", requiresAuth: false });
    }
  }

  for (const category of meta.navigation ?? []) {
    if (category.use_category_url && category.url) {
      const normalized = normalizePath(category.url, ROOT_URL);
      if (normalized) {
        upsertRoute(routeMap, {
          path: normalized,
          source: "meta:navigation-category",
          requiresAuth: inferRequiresAuth(normalized),
        });
      }
    }
    for (const item of category.urls ?? []) {
      if (!item.url) continue;
      const normalized = normalizePath(item.url, ROOT_URL);
      if (!normalized) continue;
      upsertRoute(routeMap, {
        path: normalized,
        source: "meta:navigation-link",
        requiresAuth: Boolean(item.logged_in_only) || inferRequiresAuth(normalized),
      });
    }
  }

  return routeMap;
}

async function collectInternalLinks(page: Page, baseOrigin: string) {
  const hrefs = await page.evaluate(() =>
    Array.from(document.querySelectorAll("a[href]")).map((anchor) =>
      (anchor as HTMLAnchorElement).getAttribute("href") ?? "",
    ),
  );

  const links: string[] = [];
  for (const href of hrefs) {
    const normalized = normalizePath(href, baseOrigin);
    if (!normalized || shouldExclude(normalized)) continue;
    links.push(normalized);
  }
  return links;
}

function parsePositiveInt(value: string | undefined, fallback: number) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) return fallback;
  return Math.floor(parsed);
}

function parseOptionalPositiveInt(value: string | undefined) {
  if (!value) return null;
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) return null;
  return Math.floor(parsed);
}

function parseCsvEnv(value: string | undefined) {
  if (!value) return [];
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function parseRouteRegex(value: string | undefined) {
  if (!value) return null;
  try {
    return new RegExp(value);
  } catch {
    return null;
  }
}

function dedupe(values: readonly string[]) {
  return Array.from(new Set(values));
}

function routeMatchesChunk(route: ManifestRoute, chunkName: string) {
  const chunk = ROUTE_CHUNKS[chunkName.toLowerCase()];
  if (!chunk) return false;
  const path = stripHash(route.path);
  if (chunk.exact?.includes(path)) return true;
  return (chunk.prefixes ?? []).some((prefix) => path.startsWith(prefix));
}

export function availableRouteChunks() {
  return Object.keys(ROUTE_CHUNKS).sort();
}

export function readManifestOptions(): BuildManifestOptions {
  const authModeRaw = (process.env.PLAYWRIGHT_PARITY_AUTH_MODE ?? "anon").toLowerCase();
  const authMode: AuthMode = authModeRaw === "member" ? "member" : "anon";
  return {
    authMode,
    crawlEnabled: process.env.PLAYWRIGHT_PARITY_ENABLE_CRAWL !== "0",
    maxDepth: parsePositiveInt(process.env.PLAYWRIGHT_PARITY_MAX_DEPTH, 2),
    maxPages: parsePositiveInt(process.env.PLAYWRIGHT_PARITY_MAX_PAGES, 120),
  };
}

export function filterManifestRoutes(routes: ManifestRoute[]) {
  const chunkFilters = parseCsvEnv(process.env.PLAYWRIGHT_PARITY_ROUTE_CHUNKS).map((item) => item.toLowerCase());
  const pathPrefixes = parseCsvEnv(process.env.PLAYWRIGHT_PARITY_ROUTE_PREFIXES);
  const exactPaths = parseCsvEnv(process.env.PLAYWRIGHT_PARITY_ROUTE_EXACT);
  const sourcePrefixes = parseCsvEnv(process.env.PLAYWRIGHT_PARITY_ROUTE_SOURCE_PREFIXES);
  const routeRegex = parseRouteRegex(process.env.PLAYWRIGHT_PARITY_ROUTE_REGEX);
  const limit = parseOptionalPositiveInt(process.env.PLAYWRIGHT_PARITY_ROUTE_LIMIT);

  const activeChunkFilters = dedupe(chunkFilters).filter((chunk) => ROUTE_CHUNKS[chunk]);
  const activePathPrefixes = dedupe(pathPrefixes);
  const activeExactPaths = dedupe(exactPaths);
  const activeSourcePrefixes = dedupe(sourcePrefixes);

  const filtered = routes.filter((route) => {
    const path = stripHash(route.path);

    if (activeChunkFilters.length > 0 && !activeChunkFilters.some((chunkName) => routeMatchesChunk(route, chunkName))) {
      return false;
    }

    if (activePathPrefixes.length > 0 && !activePathPrefixes.some((prefix) => path.startsWith(prefix))) {
      return false;
    }

    if (activeExactPaths.length > 0 && !activeExactPaths.includes(path)) {
      return false;
    }

    if (activeSourcePrefixes.length > 0 && !activeSourcePrefixes.some((prefix) => route.source.startsWith(prefix))) {
      return false;
    }

    if (routeRegex && !routeRegex.test(route.path)) {
      return false;
    }

    return true;
  });

  if (!limit) return filtered;
  return filtered.slice(0, limit);
}

export async function ensureAuthenticatedContext(page: Page) {
  const username = process.env.PLAYWRIGHT_PARITY_MEMBER_USERNAME ?? process.env.PLAYWRIGHT_SMOKE_USERNAME ?? "admin";
  const password = process.env.PLAYWRIGHT_PARITY_MEMBER_PASSWORD ?? process.env.PLAYWRIGHT_SMOKE_PASSWORD ?? "admin";

  const sessionBootstrap = await page.context().request.get("/api/v1/auth/session");
  expect(sessionBootstrap.ok()).toBeTruthy();

  const loginResponse = await page.context().request.post("/api/v1/auth/login", {
    data: { username, password },
  });
  expect(loginResponse.ok(), `Member login failed for user '${username}'.`).toBeTruthy();

  const sessionAfterLogin = await page.context().request.get("/api/v1/auth/session");
  expect(sessionAfterLogin.ok()).toBeTruthy();
  const payload = (await sessionAfterLogin.json()) as ApiEnvelope<{ is_authenticated?: boolean }>;
  expect(payload.data?.is_authenticated).toBe(true);
}

export async function stabilizePageForVisual(page: Page) {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.addStyleTag({
    content: `
      *, *::before, *::after {
        animation: none !important;
        transition: none !important;
        caret-color: transparent !important;
      }
      iframe, video {
        visibility: hidden !important;
      }
    `,
  });
}

export function snapshotSuffix(meta: SiteMeta) {
  const brand = meta.association_theme?.brand ?? meta.project_name ?? "default";
  return brand.toLowerCase().replace(/[^a-z0-9_-]/g, "-");
}

function hashRoute(path: string) {
  let hash = 5381;
  for (let index = 0; index < path.length; index += 1) {
    hash = ((hash << 5) + hash + path.charCodeAt(index)) >>> 0;
  }
  return hash.toString(16).padStart(8, "0");
}

export function snapshotPathForRoute(path: string, authMode: AuthMode, suffix: string) {
  const safe = path
    .replace(/^\/+/, "")
    .replace(/#\//g, "-section-")
    .replace(/[^a-z0-9/_-]/gi, "-")
    .replace(/\/+/g, "/")
    .replace(/^-+|-+$/g, "")
    .toLowerCase();
  const name = safe || "home";
  return `legacy-full/${suffix}/${authMode}/${name}-${hashRoute(path)}.png`;
}

export async function buildRouteManifest(
  request: APIRequestContext,
  page: Page,
  baseURL: string,
  options: BuildManifestOptions,
) {
  const meta = await getSiteMetaData(request);
  const routeMap = buildSeedRoutes(meta);
  const eventVariantBySlug = await expandDynamicRoutes(request, routeMap);
  const missingVariants = REQUIRED_EVENT_VARIANTS.filter(
    (variant) => !Object.values(eventVariantBySlug).includes(variant),
  );

  if (!options.crawlEnabled) {
    return {
      meta,
      manifest: {
        routes: Array.from(routeMap.values()).sort((left, right) =>
          routeSortKey(left).localeCompare(routeSortKey(right)),
        ),
        missingVariants,
        eventVariantBySlug,
      },
    };
  }

  const queue: CrawlQueueItem[] = Array.from(routeMap.values())
    .filter((route) => route.path.startsWith("/"))
    .map((route) => ({ path: stripHash(route.path), depth: 0 }));
  const crawled = new Set<string>();
  const baseOrigin = new URL(baseURL).origin;

  while (queue.length > 0 && crawled.size < options.maxPages) {
    const current = queue.shift();
    if (!current) break;
    const crawlPath = stripHash(current.path);
    if (crawled.has(crawlPath)) continue;
    if (shouldExclude(crawlPath)) continue;
    crawled.add(crawlPath);

    try {
      await page.goto(crawlPath, { waitUntil: "networkidle", timeout: 20_000 });
    } catch {
      continue;
    }

    const links = await collectInternalLinks(page, baseOrigin);
    for (const link of links) {
      const requiresAuth = inferRequiresAuth(link);
      upsertRoute(routeMap, {
        path: link,
        source: `crawl:${current.path}`,
        requiresAuth,
      });
      const enqueuePath = stripHash(link);
      if (current.depth < options.maxDepth && !crawled.has(enqueuePath)) {
        queue.push({ path: enqueuePath, depth: current.depth + 1 });
      }
    }
  }

  return {
    meta,
    manifest: {
      routes: Array.from(routeMap.values()).sort((left, right) =>
        routeSortKey(left).localeCompare(routeSortKey(right)),
      ),
      missingVariants,
      eventVariantBySlug,
    },
  };
}

export async function assertLegacyTemplateVariantParity(request: APIRequestContext) {
  const events = (await fetchApiData<EventsListItem[]>(request, "/api/v1/events?include_past=true")) ?? [];
  const mismatches: string[] = [];

  for (const event of events) {
    const detail = await fetchApiData<EventDetailItem>(request, `/api/v1/events/${event.slug}`);
    const actual = detail?.template_variant ?? "default";
    const expected = resolveLegacyVariantByTitleAndSlug(event.title, event.slug);
    if (actual !== expected) {
      mismatches.push(`${event.slug}: expected=${expected}, actual=${actual}, title="${event.title}"`);
    }
  }

  expect(
    mismatches,
    mismatches.length === 0
      ? undefined
      : `Template variant parity mismatch against legacy title-first rules:\n${mismatches.join("\n")}`,
  ).toEqual([]);
}
