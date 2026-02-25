import { validateTenantHomeConfig } from "@/lib/tenants/types";

export const demoHomeConfig = validateTenantHomeConfig("demo", {
  blocks: ["hero", "about", "news", "events", "extra", "partners"],
  showNews: true,
  showEvents: true,
});

