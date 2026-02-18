import { notFound } from "next/navigation";

import { RichContent } from "@/components/rich-content";
import { getNewsArticle } from "@/lib/api/queries";

interface LegacyNewsArticlePageProps {
  params: {
    slug: string;
  };
}

export default async function LegacyNewsArticlePage({ params }: LegacyNewsArticlePageProps) {
  const article = await getNewsArticle(params.slug).catch(() => null);
  if (!article) notFound();

  return (
    <div className="page-shell">
      <section className="hero compact">
        <p className="eyebrow">News</p>
        <h1>{article.title}</h1>
        <p className="meta">
          {article.author_name}
          {article.published_time ? ` - ${new Date(article.published_time).toLocaleDateString()}` : ""}
        </p>
      </section>
      <section className="panel">
        <RichContent html={article.content} />
      </section>
    </div>
  );
}
