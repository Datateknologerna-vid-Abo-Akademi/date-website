import type { ModuleCapability, SiteMeta } from "@/lib/api/types";

const EMPTY_MODULE_CAPABILITY: ModuleCapability = {
  enabled: false,
  routes: [],
  features: [],
};

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
