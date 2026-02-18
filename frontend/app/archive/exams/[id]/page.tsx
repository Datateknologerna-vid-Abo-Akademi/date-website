import Link from "next/link";
import { notFound } from "next/navigation";

import { getArchiveExamCollection } from "@/lib/api/queries";

interface ArchiveExamDetailPageProps {
  params: {
    id: string;
  };
  searchParams: {
    page?: string;
  };
}

export default async function ArchiveExamDetailPage({ params, searchParams }: ArchiveExamDetailPageProps) {
  const collectionId = Number(params.id);
  if (Number.isNaN(collectionId)) notFound();
  const page = Number(searchParams.page ?? "1");
  const payload = await getArchiveExamCollection(collectionId, Number.isNaN(page) ? 1 : page).catch(() => null);
  if (!payload) notFound();

  return (
    <div className="page-shell">
      <section className="hero compact">
        <p className="eyebrow">Archive</p>
        <h1>{payload.collection.title}</h1>
      </section>
      <section className="panel">
        <ul className="list list--spaced">
          {payload.results.map((document) => (
            <li key={document.id}>
              <a href={document.document_url} target="_blank" rel="noreferrer">
                {document.title}
              </a>
            </li>
          ))}
        </ul>
        <div className="pagination-row">
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
      </section>
    </div>
  );
}
