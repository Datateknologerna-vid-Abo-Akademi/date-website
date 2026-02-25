import { validateTenantHomeConfig } from "@/lib/tenants/types";

export const biocumHomeConfig = validateTenantHomeConfig("biocum", {
  blocks: ["hero", "about", "news", "events", "partners"],
  showNews: true,
  showEvents: true,
});

