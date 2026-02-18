import Link from "next/link";

import { getArchiveDocuments } from "@/lib/api/queries";
import { ensureModuleEnabled } from "@/lib/module-guards";

interface ArchiveDocumentsPageProps {
  searchParams: {
    collection?: string;
    title?: string;
    page?: string;
  };
}

export default async function ArchiveDocumentsPage({ searchParams }: ArchiveDocumentsPageProps) {
  await ensureModuleEnabled("archive");
  const page = Number(searchParams.page ?? "1");
  const payload = await getArchiveDocuments(
    searchParams.collection,
    searchParams.title,
    Number.isNaN(page) ? 1 : page,
  );

  return (
    <div className="page-shell">
      <section className="hero compact">
        <p className="eyebrow">Archive</p>
        <h1>Documents</h1>
      </section>
      <section className="panel">
        <form className="form-inline" method="get">
          <label className="form-field">
            <span>Collection</span>
            <select name="collection" defaultValue={searchParams.collection ?? ""}>
              <option value="">All</option>
              {payload.collections.map((collection) => (
                <option key={collection.id} value={collection.id}>
                  {collection.title}
                </option>
              ))}
            </select>
          </label>
          <label className="form-field">
            <span>Title contains</span>
            <input name="title" defaultValue={searchParams.title ?? ""} />
          </label>
          <button type="submit">Filter</button>
        </form>
      </section>
      <section className="panel">
        <ul className="list list--spaced">
          {payload.results.map((document) => (
            <li key={document.id}>
              <a href={document.document_url} target="_blank" rel="noreferrer">
                {document.title}
              </a>{" "}
              <span className="meta">({document.collection.title})</span>
            </li>
          ))}
        </ul>
        <div className="pagination-row">
          {payload.pagination.has_previous ? (
            <Link
              href={`/archive/documents?${new URLSearchParams({
                ...(searchParams.collection ? { collection: searchParams.collection } : {}),
                ...(searchParams.title ? { title: searchParams.title } : {}),
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
                ...(searchParams.collection ? { collection: searchParams.collection } : {}),
                ...(searchParams.title ? { title: searchParams.title } : {}),
                page: String(payload.pagination.page + 1),
              }).toString()}`}
            >
              Next
            </Link>
          ) : (
            <span />
          )}
        </div>
      </section>
    </div>
  );
}
