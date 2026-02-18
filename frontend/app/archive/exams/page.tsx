import Link from "next/link";

import { getArchiveExamCollections } from "@/lib/api/queries";
import { ensureModuleEnabled } from "@/lib/module-guards";

export default async function ArchiveExamsPage() {
  await ensureModuleEnabled("archive");
  const collections = await getArchiveExamCollections();
  return (
    <div className="page-shell">
      <section className="hero compact">
        <p className="eyebrow">Archive</p>
        <h1>Exam Collections</h1>
      </section>
      <section className="panel">
        <ul className="list list--spaced">
          {collections.map((collection) => (
            <li key={collection.id}>
              <Link href={`/archive/exams/${collection.id}`}>
                {collection.title} ({collection.item_count} files)
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
