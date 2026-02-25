import { validateTenantHomeConfig } from "@/lib/tenants/types";

export const dateHomeConfig = validateTenantHomeConfig("date", {
  blocks: ["hero", "about", "news", "events", "extra", "partners"],
  showNews: true,
  showEvents: true,
});

