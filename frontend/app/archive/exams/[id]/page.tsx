import Link from "next/link";
import { notFound } from "next/navigation";

import listStyles from "@/components/ui/list-primitives.module.css";
import { PageHero, PagePanel, PageShell } from "@/components/ui/page-shell";
import { getArchiveExamCollection } from "@/lib/api/queries";
import { ensureModuleEnabled } from "@/lib/module-guards";

interface ArchiveExamDetailPageProps {
  params: Promise<{
    id: string;
  }>;
  searchParams: Promise<{
    page?: string;
  }>;
}

export default async function ArchiveExamDetailPage({ params, searchParams }: ArchiveExamDetailPageProps) {
  await ensureModuleEnabled("archive");
  const [resolvedParams, resolvedSearchParams] = await Promise.all([params, searchParams]);
  const collectionId = Number(resolvedParams.id);
  if (Number.isNaN(collectionId)) notFound();
  const page = Number(resolvedSearchParams.page ?? "1");
  const payload = await getArchiveExamCollection(collectionId, Number.isNaN(page) ? 1 : page).catch(() => null);
  if (!payload) notFound();

  return (
    <PageShell>
      <PageHero eyebrow="Archive" title={payload.collection.title} />
      <PagePanel>
        <ul className={listStyles.listSpaced}>
          {payload.results.map((document) => (
            <li key={document.id}>
              <a href={document.document_url} target="_blank" rel="noreferrer">
                {document.title}
              </a>
            </li>
          ))}
        </ul>
        <div className={listStyles.paginationRow}>
          {payload.pagination.has_previous ? (
            <Link href={`/archive/exams/${collectionId}?page=${payload.pagination.page - 1}`}>Previous</Link>
          ) : (
            <span />
          )}
          <span className="meta">
            {payload.pagination.page} / {payload.pagination.num_pages}
          </span>
          {payload.pagination.has_next ? (
            <Link href={`/archive/exams/${collectionId}?page=${payload.pagination.page + 1}`}>Next</Link>
          ) : (
            <span />
          )}
        </div>
      </PagePanel>
    </PageShell>
  );
}
