const DEFAULT_LOCALE = "sv";
const LOCALE_COOKIE_NAME = "date_locale";
const SUPPORTED_LOCALES = ["sv", "fi"] as const;

type SupportedLocale = (typeof SUPPORTED_LOCALES)[number];

let cachedTenantDefaults: Record<string, SupportedLocale> | null = null;

function parseTenantDefaults(): Record<string, SupportedLocale> {
  if (cachedTenantDefaults) return cachedTenantDefaults;

  const raw = process.env.NEXT_PUBLIC_TENANT_DEFAULT_LOCALES ?? "{}";
  try {
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    const normalized: Record<string, SupportedLocale> = {};
    for (const [tenant, locale] of Object.entries(parsed)) {
      if (typeof locale !== "string") continue;
      const candidate = locale.toLowerCase();
      if (!SUPPORTED_LOCALES.includes(candidate as SupportedLocale)) continue;
      normalized[tenant.toLowerCase()] = candidate as SupportedLocale;
    }
    cachedTenantDefaults = normalized;
    return normalized;
  } catch {
    cachedTenantDefaults = {};
    return cachedTenantDefaults;
  }
}

function toSupportedLocale(raw: string | null | undefined): SupportedLocale | null {
  if (!raw) return null;
  const candidate = raw.toLowerCase().trim();
  return SUPPORTED_LOCALES.includes(candidate as SupportedLocale)
    ? (candidate as SupportedLocale)
    : null;
}

function pickFromAcceptLanguage(acceptLanguage: string | null): SupportedLocale | null {
  if (!acceptLanguage) return null;

  const candidates = acceptLanguage
    .split(",")
    .map((part) => part.trim().split(";")[0]?.toLowerCase())
    .filter((part): part is string => Boolean(part));

  for (const candidate of candidates) {
    const base = candidate.split("-")[0];
    const locale = toSupportedLocale(base);
    if (locale) return locale;
  }

  return null;
}

export interface LocaleResolutionInput {
  tenantSlug: string;
  explicitLocale?: string | null;
  cookieLocale?: string | null;
  acceptLanguage?: string | null;
}

export interface LocaleResolutionResult {
  locale: SupportedLocale;
  cookieName: typeof LOCALE_COOKIE_NAME;
}

export function resolveLocale(input: LocaleResolutionInput): LocaleResolutionResult {
  const tenantDefaults = parseTenantDefaults();
  const tenantDefault = tenantDefaults[input.tenantSlug.toLowerCase()] ?? DEFAULT_LOCALE;

  const locale =
    toSupportedLocale(input.explicitLocale) ??
    toSupportedLocale(input.cookieLocale) ??
    pickFromAcceptLanguage(input.acceptLanguage ?? null) ??
    tenantDefault;

  return {
    locale,
    cookieName: LOCALE_COOKIE_NAME,
  };
}

