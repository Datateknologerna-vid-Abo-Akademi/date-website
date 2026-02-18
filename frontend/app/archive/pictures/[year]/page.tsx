import Link from "next/link";
import { notFound } from "next/navigation";

import { getArchivePictureCollectionsByYear } from "@/lib/api/queries";

interface ArchivePictureYearPageProps {
  params: {
    year: string;
  };
}

export default async function ArchivePictureYearPage({ params }: ArchivePictureYearPageProps) {
  const year = Number(params.year);
  if (Number.isNaN(year)) notFound();

  const collections = await getArchivePictureCollectionsByYear(year).catch(() => null);
  if (!collections) notFound();

  return (
    <div className="page-shell">
      <section className="hero compact">
        <p className="eyebrow">Archive</p>
        <h1>Picture Albums {year}</h1>
      </section>
      <section className="panel">
        <ul className="list list--spaced">
          {collections.map((collection) => (
            <li key={collection.id}>
              <Link href={`/archive/pictures/${year}/${encodeURIComponent(collection.title)}`}>
                {collection.title} ({collection.item_count} pictures)
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
