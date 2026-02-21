import Link from "next/link";
import { notFound } from "next/navigation";

import listStyles from "@/components/ui/list-primitives.module.css";
import { PageHero, PagePanel, PageShell } from "@/components/ui/page-shell";
import { getArchivePictureCollectionsByYear } from "@/lib/api/queries";
import { ensureModuleEnabled } from "@/lib/module-guards";

interface ArchivePictureYearPageProps {
  params: Promise<{
    year: string;
  }>;
}

export default async function ArchivePictureYearPage({ params }: ArchivePictureYearPageProps) {
  await ensureModuleEnabled("archive");
  const { year: yearParam } = await params;
  const year = Number(yearParam);
  if (Number.isNaN(year)) notFound();

  const collections = await getArchivePictureCollectionsByYear(year).catch(() => null);
  if (!collections) notFound();

  return (
    <PageShell>
      <PageHero eyebrow="Archive" title={`Picture Albums ${year}`} />
      <PagePanel>
        <ul className={listStyles.listSpaced}>
          {collections.map((collection) => (
            <li key={collection.id}>
              <Link href={`/archive/pictures/${year}/${encodeURIComponent(collection.title)}`}>
                {collection.title} ({collection.item_count} pictures)
              </Link>
            </li>
          ))}
        </ul>
      </PagePanel>
    </PageShell>
  );
}
