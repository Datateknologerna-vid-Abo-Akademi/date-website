import Link from "next/link";

import { getPublications } from "@/lib/api/queries";
import { ensureModuleEnabled } from "@/lib/module-guards";
import listStyles from "@/components/ui/list-primitives.module.css";
import { PageHero, PagePanel, PageShell } from "@/components/ui/page-shell";

interface PublicationsPageProps {
  searchParams: Promise<{
    page?: string;
  }>;
}

export default async function PublicationsPage({ searchParams }: PublicationsPageProps) {
  await ensureModuleEnabled("publications");
  const resolvedSearchParams = await searchParams;
  const page = Number(resolvedSearchParams.page ?? "1");
  const payload = await getPublications(Number.isNaN(page) ? 1 : page);

  return (
    <PageShell>
      <PageHero eyebrow="Publications" title="Publication Library" />
      <PagePanel>
        <ul className={listStyles.listSpaced}>
          {payload.results.map((publication) => (
            <li key={publication.slug}>
              <h2>
                <Link href={`/publications/${publication.slug}`}>{publication.title}</Link>
              </h2>
              <p className="meta">
                {publication.publication_date
                  ? new Date(publication.publication_date).toLocaleDateString()
                  : "No publication date"}
              </p>
            </li>
          ))}
        </ul>
        <div className={listStyles.paginationRow}>
          {payload.pagination.has_previous ? (
            <Link href={`/publications?page=${payload.pagination.page - 1}`}>Previous</Link>
          ) : (
            <span />
          )}
          <span className="meta">
            {payload.pagination.page} / {payload.pagination.num_pages}
          </span>
          {payload.pagination.has_next ? (
            <Link href={`/publications?page=${payload.pagination.page + 1}`}>Next</Link>
          ) : (
            <span />
          )}
        </div>
      </PagePanel>
    </PageShell>
  );
}
