import { biocumHomeConfig } from "@/lib/tenants/biocum/home";
import { dateHomeConfig } from "@/lib/tenants/date/home";
import { demoHomeConfig } from "@/lib/tenants/demo/home";
import { kkHomeConfig } from "@/lib/tenants/kk/home";
import { onHomeConfig } from "@/lib/tenants/on/home";
import type { TenantHomeConfig } from "@/lib/tenants/types";

const HOME_CONFIG_BY_TENANT: Record<string, TenantHomeConfig> = {
  date: dateHomeConfig,
  demo: demoHomeConfig,
  kk: kkHomeConfig,
  biocum: biocumHomeConfig,
  on: onHomeConfig,
};

export function resolveTenantHomeConfig(tenantSlug: string): TenantHomeConfig {
  return HOME_CONFIG_BY_TENANT[tenantSlug] ?? dateHomeConfig;
}

