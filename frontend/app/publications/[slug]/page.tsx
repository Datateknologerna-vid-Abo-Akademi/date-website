import { notFound } from "next/navigation";

import { PageHero, PagePanel, PageShell } from "@/components/ui/page-shell";
import { getPublication } from "@/lib/api/queries";
import { ensureModuleEnabled } from "@/lib/module-guards";

interface PublicationDetailPageProps {
  params: Promise<{
    slug: string;
  }>;
}

export default async function PublicationDetailPage({ params }: PublicationDetailPageProps) {
  await ensureModuleEnabled("publications");
  const { slug } = await params;
  const publication = await getPublication(slug).catch(() => null);
  if (!publication) notFound();

  return (
    <PageShell>
      <PageHero
        eyebrow="Publications"
        title={publication.title}
        meta={
          publication.publication_date
            ? new Date(publication.publication_date).toLocaleDateString()
            : "No publication date"
        }
      />
      <PagePanel>
        {publication.description ? <p>{publication.description}</p> : null}
        <p>
          <a href={publication.pdf_url} target="_blank" rel="noreferrer">
            Open PDF
          </a>
        </p>
      </PagePanel>
    </PageShell>
  );
}
