import Image from "next/image";
import { notFound } from "next/navigation";

import { getArchivePictureCollection } from "@/lib/api/queries";

interface ArchivePictureDetailPageProps {
  params: {
    year: string;
    album: string;
  };
  searchParams: {
    page?: string;
  };
}

export default async function ArchivePictureDetailPage({
  params,
  searchParams,
}: ArchivePictureDetailPageProps) {
  const year = Number(params.year);
  if (Number.isNaN(year)) notFound();

  const page = Number(searchParams.page ?? "1");
  const payload = await getArchivePictureCollection(year, params.album, Number.isNaN(page) ? 1 : page).catch(
    () => null,
  );
  if (!payload) notFound();

  return (
    <div className="page-shell">
      <section className="hero compact">
        <p className="eyebrow">Archive</p>
        <h1>{payload.collection.title}</h1>
      </section>
      <section className="panel">
        <div className="gallery-grid">
          {payload.results.map((picture) => (
            <Image
              key={picture.id}
              src={picture.image_url}
              alt={payload.collection.title}
              width={640}
              height={480}
            />
          ))}
        </div>
        <p className="meta">
          Page {payload.pagination.page} / {payload.pagination.num_pages}
        </p>
      </section>
    </div>
  );
}
