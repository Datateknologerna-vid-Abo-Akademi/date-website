import { notFound } from "next/navigation";

import { getPublication } from "@/lib/api/queries";

interface PublicationDetailPageProps {
  params: {
    slug: string;
  };
}

export default async function PublicationDetailPage({ params }: PublicationDetailPageProps) {
  const publication = await getPublication(params.slug).catch(() => null);
  if (!publication) notFound();

  return (
    <div className="page-shell">
      <section className="hero compact">
        <p className="eyebrow">Publications</p>
        <h1>{publication.title}</h1>
        <p className="meta">
          {publication.publication_date
            ? new Date(publication.publication_date).toLocaleDateString()
            : "No publication date"}
        </p>
      </section>
      <section className="panel">
        {publication.description ? <p>{publication.description}</p> : null}
        <p>
          <a href={publication.pdf_url} target="_blank" rel="noreferrer">
            Open PDF
          </a>
        </p>
      </section>
    </div>
  );
}
