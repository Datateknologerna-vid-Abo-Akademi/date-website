import { validateTenantHomeConfig } from "@/lib/tenants/types";

export const kkHomeConfig = validateTenantHomeConfig("kk", {
  blocks: ["hero", "about", "news", "events", "partners", "instagram"],
  showNews: true,
  showEvents: true,
});

