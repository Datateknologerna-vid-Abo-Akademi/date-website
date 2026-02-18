import Link from "next/link";

import { ensureModuleEnabled } from "@/lib/module-guards";
import { isModuleEnabled } from "@/lib/modules";

export default async function ArchivePage() {
  const siteMeta = await ensureModuleEnabled("archive");
  const showPublications = isModuleEnabled(siteMeta, "publications");
  return (
    <div className="page-shell">
      <section className="hero compact">
        <p className="eyebrow">Archive</p>
        <h1>Archive Portal</h1>
        <p>Browse pictures, documents, and exams from the decoupled archive API.</p>
      </section>
      <section className="panel">
        <div className="link-grid">
          <Link href="/archive/pictures">Pictures</Link>
          <Link href="/archive/documents">Documents</Link>
          <Link href="/archive/exams">Exams</Link>
          {showPublications ? <Link href="/publications">Publications</Link> : null}
        </div>
      </section>
    </div>
  );
}
