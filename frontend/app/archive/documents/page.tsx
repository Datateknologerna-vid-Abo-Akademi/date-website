import Link from "next/link";

import { getArchiveDocuments } from "@/lib/api/queries";
import { ensureModuleEnabled } from "@/lib/module-guards";
import formStyles from "@/components/ui/form-primitives.module.css";
import listStyles from "@/components/ui/list-primitives.module.css";
import { PageHero, PagePanel, PageShell } from "@/components/ui/page-shell";

interface ArchiveDocumentsPageProps {
  searchParams: Promise<{
    collection?: string;
    title?: string;
    page?: string;
  }>;
}

export default async function ArchiveDocumentsPage({ searchParams }: ArchiveDocumentsPageProps) {
  await ensureModuleEnabled("archive");
  const resolvedSearchParams = await searchParams;
  const page = Number(resolvedSearchParams.page ?? "1");
  const payload = await getArchiveDocuments(
    resolvedSearchParams.collection,
    resolvedSearchParams.title,
    Number.isNaN(page) ? 1 : page,
  );

  return (
    <PageShell>
      <PageHero eyebrow="Archive" title="Documents" />
      <PagePanel>
        <form className={formStyles.inlineActions} method="get">
          <label className={formStyles.field}>
            <span>Collection</span>
            <select name="collection" defaultValue={resolvedSearchParams.collection ?? ""}>
              <option value="">All</option>
              {payload.collections.map((collection) => (
                <option key={collection.id} value={collection.id}>
                  {collection.title}
                </option>
              ))}
            </select>
          </label>
          <label className={formStyles.field}>
            <span>Title contains</span>
            <input name="title" defaultValue={resolvedSearchParams.title ?? ""} />
          </label>
          <button type="submit">Filter</button>
        </form>
      </PagePanel>
      <PagePanel>
        <ul className={listStyles.listSpaced}>
          {payload.results.map((document) => (
            <li key={document.id}>
              <a href={document.document_url} target="_blank" rel="noreferrer">
                {document.title}
              </a>{" "}
              <span className="meta">({document.collection.title})</span>
            </li>
          ))}
        </ul>
        <div className={listStyles.paginationRow}>
          {payload.pagination.has_previous ? (
            <Link
              href={`/archive/documents?${new URLSearchParams({
                ...(resolvedSearchParams.collection ? { collection: resolvedSearchParams.collection } : {}),
                ...(resolvedSearchParams.title ? { title: resolvedSearchParams.title } : {}),
                page: String(payload.pagination.page - 1),
              }).toString()}`}
            >
              Previous
            </Link>
          ) : (
            <span />
          )}
          <span className="meta">
            {payload.pagination.page} / {payload.pagination.num_pages}
          </span>
          {payload.pagination.has_next ? (
            <Link
              href={`/archive/documents?${new URLSearchParams({
                ...(resolvedSearchParams.collection ? { collection: resolvedSearchParams.collection } : {}),
                ...(resolvedSearchParams.title ? { title: resolvedSearchParams.title } : {}),
                page: String(payload.pagination.page + 1),
              }).toString()}`}
            >
              Next
            </Link>
          ) : (
            <span />
          )}
        </div>
      </PagePanel>
    </PageShell>
  );
}
