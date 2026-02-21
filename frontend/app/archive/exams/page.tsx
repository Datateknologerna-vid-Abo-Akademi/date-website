import Link from "next/link";

import { getArchiveExamCollections } from "@/lib/api/queries";
import { ensureModuleEnabled } from "@/lib/module-guards";
import listStyles from "@/components/ui/list-primitives.module.css";
import { PageHero, PagePanel, PageShell } from "@/components/ui/page-shell";

export default async function ArchiveExamsPage() {
  await ensureModuleEnabled("archive");
  const collections = await getArchiveExamCollections();
  return (
    <PageShell>
      <PageHero eyebrow="Archive" title="Exam Collections" />
      <PagePanel>
        <ul className={listStyles.listSpaced}>
          {collections.map((collection) => (
            <li key={collection.id}>
              <Link href={`/archive/exams/${collection.id}`}>
                {collection.title} ({collection.item_count} files)
              </Link>
            </li>
          ))}
        </ul>
      </PagePanel>
    </PageShell>
  );
}
