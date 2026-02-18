import "server-only";

import { notFound } from "next/navigation";

import { getSiteMeta } from "@/lib/api/queries";
import { isModuleEnabled } from "@/lib/modules";

export async function ensureModuleEnabled(moduleKey: string) {
  const siteMeta = await getSiteMeta();
  if (!isModuleEnabled(siteMeta, moduleKey)) {
    notFound();
  }
  return siteMeta;
}
