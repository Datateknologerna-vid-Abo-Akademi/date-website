import Link from "next/link";
import { notFound } from "next/navigation";

import { PageHero, PagePanel, PageShell } from "@/components/ui/page-shell";
import { getLuciaOverview } from "@/lib/api/queries";
import { ensureModuleEnabled } from "@/lib/module-guards";

export default async function LuciaPage() {
  await ensureModuleEnabled("lucia");
  const overview = await getLuciaOverview().catch(() => null);
  if (!overview) notFound();

  return (
    <PageShell>
      <PageHero eyebrow="Lucia" title={overview.title} meta={`Published candidates: ${overview.candidate_count}`}>
        <p>{overview.description}</p>
      </PageHero>
      <PagePanel>
        <Link href="/lucia/candidates">View candidates</Link>
      </PagePanel>
    </PageShell>
  );
}
