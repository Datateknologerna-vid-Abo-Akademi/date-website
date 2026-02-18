import type { ModuleCapability, SiteMeta } from "@/lib/api/types";

const EMPTY_MODULE_CAPABILITY: ModuleCapability = {
  enabled: false,
  routes: [],
  features: [],
};

const MODULE_NAV_ORDER = [
  "news",
  "events",
  "polls",
  "archive",
  "social",
  "ads",
  "publications",
  "ctf",
  "lucia",
  "alumni",
] as const;

const MODULE_NAV_EXCLUDED = new Set(["billing", "staticpages"]);

export interface ModuleNavItem {
  moduleKey: string;
  label: string;
  href: string;
}

export function getModuleCapability(siteMeta: SiteMeta, moduleKey: string): ModuleCapability {
  const capability = siteMeta.module_capabilities?.[moduleKey];
  if (capability) {
    return capability;
  }
  const enabled = siteMeta.enabled_modules.includes(moduleKey);
  if (!enabled) {
    return EMPTY_MODULE_CAPABILITY;
  }
  return {
    enabled: true,
    routes: [],
    features: [],
  };
}

export function isModuleEnabled(siteMeta: SiteMeta, moduleKey: string) {
  return getModuleCapability(siteMeta, moduleKey).enabled;
}

export function moduleHasFeature(siteMeta: SiteMeta, moduleKey: string, feature: string) {
  const capability = getModuleCapability(siteMeta, moduleKey);
  return capability.enabled && capability.features.includes(feature);
}

function humanizeModuleKey(moduleKey: string) {
  return moduleKey.charAt(0).toUpperCase() + moduleKey.slice(1);
}

function resolveModuleNavRoute(capability: ModuleCapability) {
  if (typeof capability.nav_route === "string" && capability.nav_route.startsWith("/")) {
    return capability.nav_route;
  }
  return capability.routes.find((route) => route.startsWith("/") && !route.includes("{")) ?? "";
}

function moduleNavSortIndex(moduleKey: string) {
  const index = MODULE_NAV_ORDER.indexOf(moduleKey as (typeof MODULE_NAV_ORDER)[number]);
  return index === -1 ? Number.MAX_SAFE_INTEGER : index;
}

export function getModuleNavigation(siteMeta: SiteMeta): ModuleNavItem[] {
  const items = Object.entries(siteMeta.module_capabilities ?? {})
    .filter(([moduleKey, capability]) => capability.enabled && !MODULE_NAV_EXCLUDED.has(moduleKey))
    .map(([moduleKey, capability]) => {
      const href = resolveModuleNavRoute(capability);
      if (!href) {
        return null;
      }
      return {
        moduleKey,
        href,
        label: capability.label?.trim() || humanizeModuleKey(moduleKey),
      };
    })
    .filter((item): item is ModuleNavItem => item !== null);

  items.sort((left, right) => {
    const orderDiff = moduleNavSortIndex(left.moduleKey) - moduleNavSortIndex(right.moduleKey);
    if (orderDiff !== 0) {
      return orderDiff;
    }
    return left.label.localeCompare(right.label);
  });

  return items;
}
