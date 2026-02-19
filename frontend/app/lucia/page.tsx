import Link from "next/link";
import { notFound } from "next/navigation";

import { getLuciaOverview } from "@/lib/api/queries";
import { ensureModuleEnabled } from "@/lib/module-guards";

export default async function LuciaPage() {
  await ensureModuleEnabled("lucia");
  const overview = await getLuciaOverview().catch(() => null);
  if (!overview) notFound();

  return (
    <div className="page-shell">
      <section className="hero compact">
        <p className="eyebrow">Lucia</p>
        <h1>{overview.title}</h1>
        <p>{overview.description}</p>
        <p className="meta">Published candidates: {overview.candidate_count}</p>
      </section>
      <section className="panel">
        <Link href="/lucia/candidates">View candidates</Link>
      </section>
    </div>
  );
}
