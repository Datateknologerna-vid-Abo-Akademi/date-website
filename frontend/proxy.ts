import { NextResponse, type NextRequest } from "next/server";

import { resolveLocale } from "@/lib/i18n/resolve-locale";
import { resolveTenant } from "@/lib/tenant/resolver";

export function proxy(request: NextRequest) {
  const host = request.headers.get("x-forwarded-host") ?? request.headers.get("host") ?? "";
  const resolution = resolveTenant(host, request.nextUrl.pathname);

  const localeResolution = resolveLocale({
    tenantSlug: resolution.tenantSlug,
    explicitLocale: request.headers.get("x-locale"),
    cookieLocale: request.cookies.get("date_locale")?.value,
    acceptLanguage: request.headers.get("accept-language"),
  });

  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-tenant-slug", resolution.tenantSlug);
  requestHeaders.set("x-locale", localeResolution.locale);
  requestHeaders.set("x-original-host", host);
  if (host) requestHeaders.set("x-forwarded-host", host);

  const shouldRewritePath = resolution.normalizedPath !== request.nextUrl.pathname;
  const response = shouldRewritePath
    ? NextResponse.rewrite(
        new URL(
          `${resolution.normalizedPath}${request.nextUrl.search}`,
          request.url,
        ),
        {
          request: { headers: requestHeaders },
        },
      )
    : NextResponse.next({
        request: { headers: requestHeaders },
      });

  const hasLocaleCookie = request.cookies.has(localeResolution.cookieName);
  if (!hasLocaleCookie) {
    response.cookies.set(localeResolution.cookieName, localeResolution.locale, {
      sameSite: "lax",
      path: "/",
      httpOnly: false,
    });
  }

  return response;
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|api|static|media|healthz).*)",
  ],
};

