import { notFound } from "next/navigation";

import { RichContent } from "@/components/rich-content";
import { getStaticPage } from "@/lib/api/queries";

interface StaticPageProps {
  params: {
    slug: string;
  };
}

export default async function StaticPageDetail({ params }: StaticPageProps) {
  const { slug } = params;
  const page = await getStaticPage(slug).catch(() => null);
  if (!page) {
    notFound();
  }
  return (
    <div className="page-shell">
      <section className="hero compact">
        <p className="eyebrow">Page</p>
        <h1>{page.title}</h1>
      </section>
      <section className="panel">
        <RichContent html={page.content} />
      </section>
    </div>
  );
}
