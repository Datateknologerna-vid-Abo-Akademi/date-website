import Link from "next/link";

import { ensureModuleEnabled } from "@/lib/module-guards";
import listStyles from "@/components/ui/list-primitives.module.css";
import { PageHero, PagePanel, PageShell } from "@/components/ui/page-shell";

export default async function AlumniPage() {
  await ensureModuleEnabled("alumni");

  return (
    <PageShell>
      <PageHero eyebrow="Alumni" title="Alumni Portal" />
      <PagePanel>
        <div className={listStyles.linkGrid}>
          <Link href="/alumni/signup">Register</Link>
          <Link href="/alumni/update">Request update token</Link>
        </div>
      </PagePanel>
    </PageShell>
  );
}
