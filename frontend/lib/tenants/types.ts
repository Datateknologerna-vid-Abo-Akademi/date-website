export type HomeBlockKey =
  | "hero"
  | "about"
  | "news"
  | "events"
  | "extra"
  | "partners"
  | "instagram";

export interface TenantHomeConfig {
  blocks: HomeBlockKey[];
  showNews: boolean;
  showEvents: boolean;
}

const ALLOWED_BLOCKS: readonly HomeBlockKey[] = [
  "hero",
  "about",
  "news",
  "events",
  "extra",
  "partners",
  "instagram",
];

export function validateTenantHomeConfig(tenantSlug: string, config: TenantHomeConfig): TenantHomeConfig {
  const seen = new Set<string>();
  for (const block of config.blocks) {
    if (!ALLOWED_BLOCKS.includes(block)) {
      throw new Error(`Invalid home block '${block}' for tenant '${tenantSlug}'.`);
    }
    if (seen.has(block)) {
      throw new Error(`Duplicate home block '${block}' for tenant '${tenantSlug}'.`);
    }
    seen.add(block);
  }
  return config;
}

