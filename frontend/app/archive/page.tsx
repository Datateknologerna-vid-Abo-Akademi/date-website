import Link from "next/link";

import { ensureModuleEnabled } from "@/lib/module-guards";
import { isModuleEnabled } from "@/lib/modules";
import listStyles from "@/components/ui/list-primitives.module.css";
import { PageHero, PagePanel, PageShell } from "@/components/ui/page-shell";

export default async function ArchivePage() {
  const siteMeta = await ensureModuleEnabled("archive");
  const showPublications = isModuleEnabled(siteMeta, "publications");
  return (
    <PageShell>
      <PageHero eyebrow="Archive" title="Archive Portal">
        <p>Browse pictures, documents, and exams from the decoupled archive API.</p>
      </PageHero>
      <PagePanel>
        <div className={listStyles.linkGrid}>
          <Link href="/archive/pictures">Pictures</Link>
          <Link href="/archive/documents">Documents</Link>
          <Link href="/archive/exams">Exams</Link>
          {showPublications ? <Link href="/publications">Publications</Link> : null}
        </div>
      </PagePanel>
    </PageShell>
  );
}
