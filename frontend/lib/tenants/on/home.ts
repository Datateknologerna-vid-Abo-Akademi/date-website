import { validateTenantHomeConfig } from "@/lib/tenants/types";

export const onHomeConfig = validateTenantHomeConfig("on", {
  blocks: ["hero", "about", "news", "events", "partners"],
  showNews: true,
  showEvents: true,
});

