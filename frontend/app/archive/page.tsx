import Link from "next/link";

export default function ArchivePage() {
  return (
    <div className="page-shell">
      <section className="hero compact">
        <p className="eyebrow">Archive</p>
        <h1>Archive Portal</h1>
        <p>Browse pictures, documents, and exams from the decoupled archive API.</p>
      </section>
      <section className="panel">
        <div className="link-grid">
          <Link href="/archive/pictures">Pictures</Link>
          <Link href="/archive/documents">Documents</Link>
          <Link href="/archive/exams">Exams</Link>
          <Link href="/publications">Publications</Link>
        </div>
      </section>
    </div>
  );
}
