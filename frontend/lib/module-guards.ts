import "server-only";

import { cache } from "react";
import { notFound } from "next/navigation";

import { getSiteMeta } from "@/lib/api/queries";
import { isModuleEnabled } from "@/lib/modules";

const getSiteMetaCached = cache(getSiteMeta);

export async function ensureModuleEnabled(moduleKey: string) {
  const siteMeta = await getSiteMetaCached();
  if (!isModuleEnabled(siteMeta, moduleKey)) {
    notFound();
  }
  return siteMeta;
}
