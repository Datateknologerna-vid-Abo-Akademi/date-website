const DEFAULT_TENANT = "date";

let cachedHostMap: Record<string, string> | null = null;

function normalizeHost(rawHost: string): string {
  return rawHost.trim().toLowerCase().replace(/:\d+$/, "");
}

function parseHostMapEnv(): Record<string, string> {
  if (cachedHostMap) return cachedHostMap;

  const raw = process.env.NEXT_PUBLIC_TENANT_HOST_MAP ?? process.env.TENANT_HOST_MAP ?? "{}";
  try {
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    const normalized: Record<string, string> = {};
    for (const [host, tenant] of Object.entries(parsed)) {
      if (typeof tenant !== "string" || tenant.trim().length === 0) continue;
      const normalizedHost = normalizeHost(host);
      if (!normalizedHost) continue;
      normalized[normalizedHost] = tenant.trim().toLowerCase();
    }
    cachedHostMap = normalized;
    return normalized;
  } catch {
    cachedHostMap = {};
    return cachedHostMap;
  }
}

export interface TenantResolutionResult {
  tenantSlug: string;
  source: "host" | "path" | "default";
  normalizedPath: string;
}

export function extractTenantFromPath(pathname: string): { tenantSlug: string; normalizedPath: string } | null {
  const match = pathname.match(/^\/t\/([a-z0-9-]+)(\/.*)?$/i);
  if (!match) return null;

  const tenantSlug = match[1].toLowerCase();
  const remainder = match[2] && match[2].length > 0 ? match[2] : "/";
  return {
    tenantSlug,
    normalizedPath: remainder,
  };
}

export function resolveTenant(hostname: string, pathname: string): TenantResolutionResult {
  const hostMap = parseHostMapEnv();
  const normalizedHost = normalizeHost(hostname);
  const tenantFromHost = normalizedHost ? hostMap[normalizedHost] : undefined;

  if (tenantFromHost) {
    return {
      tenantSlug: tenantFromHost,
      source: "host",
      normalizedPath: pathname,
    };
  }

  const fromPath = extractTenantFromPath(pathname);
  if (fromPath) {
    return {
      tenantSlug: fromPath.tenantSlug,
      source: "path",
      normalizedPath: fromPath.normalizedPath,
    };
  }

  return {
    tenantSlug: process.env.NEXT_PUBLIC_DEFAULT_TENANT?.toLowerCase() ?? DEFAULT_TENANT,
    source: "default",
    normalizedPath: pathname,
  };
}

